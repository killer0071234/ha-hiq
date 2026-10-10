# Spec: Module card id and firmware in device info

Issue: [#298](https://github.com/killer0071234/ha-hiq/issues/298)

## Objective

Newer HIQ controllers report two variables for every expansion module
(`mmNN`, e.g. `lc00`, `ld01`, `bc00`, `th00`):

- `cNAD.mmNN_iex_card_id`: hardware code of the connected module
  (e.g. `60` = LC-10-IQ), `0` = none
- `cNAD.mmNN_firmware_version`: firmware as a 4-digit decimal number
  (major, minor, build, release)

Today every device shows the same static info: model `HIQ controller`,
`sw_version` = the integration version (`0.4.1`) and `hw_version` = `2/3`.
Thermostat devices show no model or version at all; they get the same defaults
as the other devices.

Read both variables at startup and use them in the device info of the module's
devices, so users can see in Home Assistant which module type and firmware is
installed.

### User stories

- As a user, I can see on a light, blind or thermostat device which module it
  belongs to (e.g. `LC-10-IQ`, `TH-1-IQ`) and which firmware that module runs.
- As a user with an older controller (no such variables) or a slot with no
  module, my devices look exactly as they do today.

## Assumptions

1. **Existing devices only.** No new devices, the device tree stays the same.
   Every device that belongs to a module gets that module's info:

   | Module | Devices (unchanged identifiers) | Built in |
   |---|---|---|
   | `lcNN`, `ldNN` | one device per light output (`Light cNAD.lcNN_qxMM`) | `light._light_device_info` |
   | `bcNN` | one device per blind (`Blind cNAD.bcNN_blinds_position_MM`) | `cover.py` |
   | `thNN` | one device per thermostat (`cNAD.thNN thermostat`) | `models.thermostat_device_info` |

   `scNN` and `fcNN` modules have no device of their own (their sensors live on
   shared devices such as `cNAD temperatures`) and are out of scope.
2. **Model** comes from a fixed table in `const.py`:

   `IEX_CARD_MODELS` holds the full list provided by the maintainer (card ids
   1 .. 208 and 9999, e.g. `60` LC-10-IQ, `63` BC-5-IQ, `64` SC-4-IQ,
   `65` TH-1-IQ, `66` TH-2-IQ, `67` FC-1-IQ, `72` LD-D10-IQ), the ids only
   found in the CyPro 2.8.0c hardware list (`4`, `8`, `9`, `17`, `32`, `34`,
   `37`, `47`, `49`, `53`, `54`, `137`) and `69` TH-3-IQ, plus `70` TH-1T and
   `71` SC-4T from the controller's variable descriptions.
   Card id `0` (listed as `BCM`) means no module and is never looked up.

   An unknown, non-zero card id is shown as `card <id>` (e.g. `card 99`).
3. **Firmware** is a 16 bit integer (`1..32767`). The last three digits are
   minor, build and release (one digit each), everything before them is the
   major version: `major.minor.build.release` =
   `v // 1000`, `v // 100 % 10`, `v // 10 % 10`, `v % 10`.
   `32767` → `32.7.6.7`, `1203` → `1.2.0.3`, `1000` → `1.0.0.0`,
   `1` → `0.0.0.1`. A negative value counts as missing.
4. **Missing values.** A variable is *missing* if the controller does not list
   it (older controller), or its value is `0` (no module), `?` (not readable)
   or not an integer (for firmware also a negative value).

   | Card id | Firmware | model | sw_version |
   |---|---|---|---|
   | missing | missing | `HIQ controller` | integration version |
   | present | missing | from card id | `unknown` |
   | missing | present | `unknown` | from firmware |
   | present | present | from card id | from firmware |
5. Thermostat devices get the same defaults as light and blind devices:
   model `HIQ controller`, `sw_version` = integration version,
   `hw_version` = `2/3` and `configuration_url`. Identifiers, name and
   suggested area stay unchanged. `hw_version` is never taken from the module.
6. **Read once at startup**, together with the module error tags in
   `async_setup_entry`, before the platforms are set up (same mechanism as the
   `_general_error` and `_rgb_mode` tags). A module firmware update shows after
   the entry is reloaded. The variables are not polled afterwards beyond what
   that pre-read registers.
7. Only the variables that exist in the controller's variable list are read
   (no requests for tags of older controllers).

## Tech Stack

- Python 3.13+, Home Assistant 2026.9.4, `cybro` 0.4.1
- Tests: `pytest` + `pytest-homeassistant-custom-component`
- Lint/format: `ruff`

## Commands

```
Test:      scripts/test                      # pytest --cov --cov-report=term
Single:    scripts/test tests/test_models.py
Live:      HIQ_LIVE_HOST=192.168.1.10 HIQ_LIVE_NAD=1000 scripts/test tests/live
Lint:      scripts/lint                      # ruff check . --fix
Format:    ruff format .
```

## Project Structure

```
custom_components/hiq/
  __init__.py      → pre-read *_iex_card_id / *_firmware_version at startup
  const.py         → card id → model table
  models.py        → helper returning model / sw_version of a module;
                     thermostat_device_info uses it
  light.py         → _light_device_info uses it
  cover.py         → blind device info uses it
tests/
  fake_controller.py → card id / firmware tags for the test modules
  test_models.py     → new: helper (table, unknown id, fallbacks, firmware format)
  test_init.py / test_light.py / test_cover.py / test_climate.py
                     → device registry shows model / sw_version per module
README.md          → mention module model / firmware in device info
```

## Code Style

Follow the existing helpers in `models.py`: small functions taking the
coordinator, docstring on every function, values read with
`coordinator.data.vars`. Expected shape:

```python
def module_device_info(
    coordinator: HiqDataUpdateCoordinator, module: str
) -> dict[str, str]:
    """Return model and sw_version of a module (eg: c1000.lc00), if reported."""
    card_id = _int_value(coordinator, f"{module}_iex_card_id")
    firmware = _int_value(coordinator, f"{module}_firmware_version")
    if card_id is None and firmware is None:
        return {}  # older controller, keep the defaults
    return {
        "model": _card_model(card_id),  # None -> "unknown"
        "sw_version": _firmware(firmware),  # None -> "unknown"
    }
```

Callers merge it over today's defaults (a dict merge, as passing `model=`
and `**info` together raises a duplicate keyword error):

```python
versions = {"model": DEVICE_DESCRIPTION, "sw_version": DEVICE_SW_VERSION}
DeviceInfo(..., **(versions | module_device_info(coordinator, module)))
```

## Testing Strategy

Write the tests first. Unit tests for the helper, integration tests through the
device registry using `setup_with_tags` / the fake controller.

- Helper (`test_models.py`): every table entry, unknown id → `card <id>`,
  every row of the missing-values table (missing = not listed / `0` / `?` /
  non-numeric, each kind tested), firmware `1203` → `1.2.0.3`,
  `1000` → `1.0.0.0`, `1` → `0.0.0.1`, `10000` → `10.0.0.0`,
  `32767` → `32.7.6.7`, negative → missing.
- Device registry: a light output, a blind and a thermostat with card id and
  firmware show the module model and firmware. All outputs of one module show
  the same values.
- Regression: a controller without these variables gives light and blind
  devices identical to today (model, sw_version, hw_version, identifiers,
  names); thermostat devices keep identifiers and names and get the defaults.
- No extra request for variables missing from the controller's variable list.
- Live (read-only, existing `tests/live`): setup stays free of warnings; on
  c10000 the `th01` thermostat device shows `TH-2-IQ` / `1.0.0.0` and the `th00`
  device (both `0`) shows `HIQ controller` / integration version.

Coverage of the touched modules must not drop.

## Boundaries

- **Always:** write tests first; run `scripts/test` and `scripts/lint`; keep
  device identifiers and names unchanged.
- **Ask first:** creating new devices or changing the device tree; taking
  `hw_version` from the module; polling these variables continuously; adding models for card
  ids not in the table above.
- **Never:** change unique ids, entity ids or device identifiers; write to the
  controller; fail setup because these variables are missing or invalid.

## Success Criteria

1. With card id `60` and firmware `1203` on `lc00`, every light device of
   `lc00` shows model `LC-10-IQ` and software `1.2.0.3`.
2. The same works for `ld` lights (`LD-D10-IQ`), blinds (`BC-5-IQ`) and thermostats
   (`TH-1-IQ`, `TH-2-IQ`, `TH-3-IQ`, `TH-1T`).
3. An unknown card id shows `card <id>`. If only one of card id and firmware
   is missing (incl. `0`), it shows `unknown` and the other one is shown.
4. With both variables missing (incl. `0`), light and blind devices are identical to today, and thermostat devices show the same defaults as them
   (`HIQ controller`, integration version, `2/3`).
5. The variables are read once at startup, before the platforms are set up,
   and only if the controller lists them.
6. `scripts/test`, `scripts/lint` and `ruff format --check .` pass, and
   coverage of the touched modules does not drop.

## Open Questions

None.

## Resolved Decisions

1. Existing devices get the module info; no new devices.
2. Model from a fixed card id table; firmware as dotted digits; per-field
   fallback to the defaults.
3. Thermostat devices get the same defaults as light / blind devices.
4. Card id 69 found in the tag description on c8372 (named TH-3-IQ, see 10).
5. Firmware format (one digit each for minor, build, release) seen on c10000:
   `th01` (card 66, TH-2-IQ) reports `1000` → `1.0.0.0`, `fc00` (card 67, FC-1-IQ)
   reports `1` → `0.0.0.1`.
6. A value of `0` counts as missing.
7. Both variables missing → defaults (`HIQ controller` / integration version);
   only one missing → the other is shown and the missing one is `unknown`.
8. Firmware may be up to `32767`: the major version takes all digits before
   the last three (`32767` → `32.7.6.7`).
9. Card id table replaced by the maintainer's full list (names with `-IQ`
   suffix win over the controller descriptions); 70, 71 kept from the
   descriptions; `0` stays missing although the list names it `BCM`.
10. Ids only in the CyPro 2.8.0c hardware list are added; on conflicts the
    maintainer's list wins (2, 7, 26, 50, 72 unchanged). Card 69 is `TH-3-IQ`.
