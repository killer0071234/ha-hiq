# Implementation Plan: Module card id and firmware in device info

Spec: [SPEC.md](../SPEC.md) · Tasks: [todo.md](todo.md) · Issue: #298

## Overview

Read `mmNN_iex_card_id` and `mmNN_firmware_version` once at startup and show
them as `model` / `sw_version` on the existing light, blind and thermostat
devices. One helper in `models.py` turns the two values into device info
fields. Each device builder merges that over the shared defaults
(`HIQ controller`, integration version). If both values are missing (incl.
`0`), the defaults stay as they are.

## Architecture Decisions

- **One helper, three callers.** `module_device_info(coordinator, module)` in
  `models.py` returns `{}` (both missing) or `{"model": …, "sw_version": …}`.
  The callers are `light._light_device_info`, the blind `DeviceInfo` in
  `cover.py` and `models.thermostat_device_info`. All entities of one
  thermostat (climate, sensors, numbers, selects, switches, buttons) already
  share `thermostat_device_info`, so they stay consistent without extra work.
- **Module prefix from the tag.** The module is the tag up to the first `_`
  (`c1000.lc00_qx03` → `c1000.lc00`, `c1000.th00` → itself), the same split the
  code already uses for `_general_error`.
- **Read in the existing startup pre-read.** Extend the regex in
  `async_setup_entry` with `_iex_card_id|_firmware_version`. Only listed
  variables are added (iterates `plc_info.plc_vars`), so older controllers get
  no extra requests. No separate poll.
- **Card id table in `const.py`** (`IEX_CARD_MODELS: dict[int, str]`), next to
  the other device constants.
- **Firmware format** as a small pure function:
  `f"{v // 1000}.{v // 100 % 10}.{v // 10 % 10}.{v % 10}"`.
- **Thermostat defaults** are added to `thermostat_device_info` itself
  (`model`, `sw_version`, `hw_version`, `configuration_url`), so all thermostat
  entities change together.

## Dependency Graph

```
T1 helper + table (models.py, const.py)
 ├── T2 startup pre-read + thermostat devices   (first caller, proves the read)
 │    ├── T3 light devices
 │    └── T4 blind devices
 └──────────── T5 live check + README
```

T3 and T4 are independent of each other once T2 is done.

## Task List

### Phase 1: Foundation
- [x] Task 1: Module device info helper and card id table

### Phase 2: Devices
- [x] Task 2: Read module info at startup, show it on thermostat devices
- [x] Task 3: Show module info on light devices
- [x] Task 4: Show module info on blind devices

### Checkpoint: Devices
- [x] `scripts/test`, `scripts/lint` green; review with the user

### Phase 3: Finish
- [x] Task 5: Live check and README

### Checkpoint: Complete
- [x] All SPEC success criteria met, ready for review

## Risks and Mitigations

| Risk | Impact | Mitigation |
|---|---|---|
| Adding card id / firmware tags to the default fake controller changes devices in unrelated tests | Med | Add them only to the modules under test (th00, lc00, ld01, bc00). Run the full suite after T2. |
| Thermostat devices now get `hw_version` / `configuration_url`, so existing thermostat device assertions change | Low | Intended (spec decision 3). Update the assertions and say so in the commit. |
| Device registry keeps old values until reload | Low | Expected: read once at startup (spec assumption 6). |
| Firmware format only seen on two test values | Low | Format fixed in spec decision 8 (up to `32767`), unit-tested at the edges. |

## Open Questions

None.
