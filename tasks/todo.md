# Tasks: Module card id and firmware in device info

See [plan.md](plan.md) and [SPEC.md](../SPEC.md). Write the tests first in every task.

## Task 1: Module device info helper and card id table

**Description:** Add `IEX_CARD_MODELS` (maintainer's full list, e.g. 60 LC-10-IQ, 63 BC-5-IQ, 64 SC-4-IQ, 65 TH-1-IQ,
66 TH-2-IQ, 67 FC-1-IQ, 72 LD-D10-IQ, 69 TH-3-IQ, CyPro-only ids, plus 70 TH-1T, 71 SC-4T) to `const.py`, and
`module_device_info(coordinator, module)` to `models.py`. The helper reads
`{module}_iex_card_id` / `{module}_firmware_version` from
`coordinator.data.vars`. A value is missing if it is not listed, `0`, `?` or
not an integer (firmware: also negative).

**Acceptance criteria:**
- [x] Both missing → `{}`. One missing → that field is `unknown` and the other is shown. Both present → model and firmware.
- [x] Every table entry maps to its model, and an unknown id gives `card <id>`.
- [x] Firmware `32767` → `32.7.6.7`, `10000` → `10.0.0.0`, `1203` → `1.2.0.3`, `1000` → `1.0.0.0`, `1` → `0.0.0.1`.

**Verification:**
- [x] `scripts/test tests/test_models.py` (new)
- [x] `scripts/lint`

**Dependencies:** None

**Files likely touched:** `custom_components/hiq/const.py`,
`custom_components/hiq/models.py`, `tests/test_models.py`

**Estimated scope:** S

## Task 2: Read module info at startup, show it on thermostat devices

**Description:** Extend the startup pre-read regex in `async_setup_entry` with
`_iex_card_id|_firmware_version`. `thermostat_device_info` gets the shared
defaults (`HIQ controller`, integration version, `2/3`, configuration URL)
with `module_device_info` merged over them.

**Acceptance criteria:**
- [x] A thermostat with card id `66` and firmware `1000` shows device model `TH-2-IQ` and sw_version `1.0.0.0`. The values are read before the platforms are set up.
- [x] A thermostat without these variables shows `HIQ controller` / integration version / `2/3`. Identifiers and name are unchanged.
- [x] No request contains `_iex_card_id` / `_firmware_version` tags that the controller doesn't list.

**Verification:**
- [x] `scripts/test tests/test_climate.py tests/test_init.py`
- [x] `scripts/test` (full suite: fake controller tags changed)

**Dependencies:** T1

**Files likely touched:** `custom_components/hiq/__init__.py`,
`custom_components/hiq/models.py`, `tests/fake_controller.py`,
`tests/test_climate.py`, `tests/test_init.py`

**Estimated scope:** M

## Task 3: Show module info on light devices

**Description:** `_light_device_info` merges `module_device_info` for the
output's module (`cNAD.lcNN` / `cNAD.ldNN`) over today's model / sw_version.

**Acceptance criteria:**
- [x] Every output device of `lc00` with card id `60` shows `LC-10-IQ` and the module firmware. `ld` modules show `LD-D10-IQ`.
- [x] Light devices without these variables are identical to today.

**Verification:**
- [x] `scripts/test tests/test_light.py`

**Dependencies:** T2

**Files likely touched:** `custom_components/hiq/light.py`,
`tests/fake_controller.py`, `tests/test_light.py`

**Estimated scope:** S

## Task 4: Show module info on blind devices

**Description:** The blind `DeviceInfo` in `cover.py` merges
`module_device_info` for `cNAD.bcNN` over today's model / sw_version.

**Acceptance criteria:**
- [x] A blind of `bc00` with card id `63` shows `BC-5-IQ` and the module firmware.
- [x] Blind devices without these variables are identical to today.

**Verification:**
- [x] `scripts/test tests/test_cover.py`

**Dependencies:** T2

**Files likely touched:** `custom_components/hiq/cover.py`,
`tests/fake_controller.py`, `tests/test_cover.py`

**Estimated scope:** S

## Checkpoint: Devices
- [x] `scripts/test` and `scripts/lint` are green, and coverage of the touched modules has not dropped
- [x] Review with the user before continuing

## Task 5: Live check and README

**Description:** Extend the read-only live test: on the controller, `th01`
shows `TH-2-IQ` / `1.0.0.0` and `th00` keeps the defaults. Document the module
model / firmware in the README.

**Acceptance criteria:**
- [x] The live test passes against a live controller (`HIQ_LIVE_HOST=192.168.1.10 HIQ_LIVE_NAD=1000`).
- [x] The README says where model and firmware come from, and what `unknown` means.
- [x] All SPEC success criteria are checked.

**Verification:**
- [x] `HIQ_LIVE_HOST=192.168.1.10 HIQ_LIVE_NAD=1000 scripts/test tests/live`
- [x] `scripts/test`, `scripts/lint`, `ruff format --check .`

**Dependencies:** T3, T4

**Files likely touched:** `tests/live/test_live.py`, `README.md`

**Estimated scope:** S

## Checkpoint: Complete
- [x] All acceptance criteria met
- [x] Ready for review
