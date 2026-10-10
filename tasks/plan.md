# Implementation Plan: Custom select entities

Spec: [SPEC.md](../SPEC.md) · Tasks: [todo.md](todo.md)

## Overview

Add user-configured `select` entities (integer PLC tag + `label=value` options)
to the options flow. The flow moves to a unified add / edit / remove entity
menu that covers both custom sensors and custom selects. Selects are stored in
`entry.options["select"]` and live on the shared `c{nad} custom` device.

## Architecture Decisions

- **Menu refactor first, with no change in behaviour.** It touches the existing
  sensor tests, so it lands alone and stays green before any select code exists.
  That isolates the riskiest change.
- **Entity before flow.** Custom selects are first built from
  `entry.options["select"]` that tests seed directly. The flow then only has to
  produce that stored shape, which keeps each slice small and testable on its own.
- **Reuse `HiqSelectEntity`.** It already maps labels to integers and writes with
  `write_var` when `var_write_req is None`. Its existing `unique_id` parameter
  covers the uuid.
- **Add branches through an `add_entity` sub-menu. Edit branches through a
  callable `next_step`.** The callable only receives the options, so the edited
  platform is kept in a transient `_edit_platform` key there. The edit step
  removes it again.
- **Edit/remove keys `"<platform>:<index>"`**, parsed by one helper, used by both
  steps.
- **Options stored as `{label: int}`.** The form takes a multi-value
  `SelectSelector(custom_value=True)` of `label=value` strings. One parse helper
  validates and converts them, and one format helper turns the mapping back into
  strings for edit.
- **Device info for `c{nad} custom`** is extracted into `models.py`, so sensor
  and select build the identical device.

## Dependency Graph

```
T1 menu refactor ─────────────┐
T2 select entity from options ┼─→ T3 add_select ─→ T4 edit_select ─→ T5 remove/mixed ─→ T6 docs
```

T1 and T2 are independent of each other. T3 needs both.

## Task List

### Phase 1: Foundation
- [x] T1: Unified options menu (sensors only, behaviour unchanged)
- [x] T2: Custom select entities from `entry.options["select"]`

### Checkpoint: Foundation
- [x] `scripts/test` and `scripts/lint` pass. Existing sensor tests pass with only their step ids changed.

### Phase 2: Flow
- [x] T3: Add custom select via options flow, with validation
- [ ] T4: Edit custom select
- [ ] T5: Remove custom selects (incl. mixed sensor + select removal)

### Checkpoint: Flow
- [ ] Full add → edit → remove cycle works for both types. Registry cleanup is verified.
- [ ] Manual check in dev HA (`scripts/develop`)

### Phase 3: Polish
- [ ] T6: README section and final pass

### Checkpoint: Complete
- [ ] All SPEC success criteria met. Coverage of touched modules has not dropped.

## Risks and Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| Menu refactor breaks existing sensor flow/tests | High | Do it in T1 alone. Change only step ids in the tests, keep the assertions. |
| `SelectSelector(multiple, custom_value)` round-trip on edit doesn't prefill as expected | Med | Cover the edit prefill (suggested values) with a test in T4. |
| `test_consistency.py` fails when strings.json / en.json / de.json drift | Med | Update all three in the same task as each new step or error. |
| Entity id of custom sensors changes because of device-info extraction | High | Regression test in T1: entry with only `"sensor"` keeps unique id and entity id. |
| Stored `{label: int}` keys come back in a different order after JSON round-trip | Low | Dicts keep insertion order through JSON. The T2 test asserts option order. |

## Open Questions

None. All were resolved in SPEC.md.
