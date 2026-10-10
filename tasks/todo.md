# Tasks: Custom select entities

See [plan.md](plan.md) and [SPEC.md](../SPEC.md). Write the tests first in every task.

## Task 1: Unified options menu (sensors only)

**Description:** Replace the `add_sensor / select_edit_sensor / remove_sensor`
menu with `add_entity / select_edit_entity / remove_entity`.
`add_entity` asks for the type and only offers `sensor` for now; a callable
`next_step` routes to `add_sensor`. Edit/remove lists use `"sensor:<idx>"` keys
and `"<name> (Sensor)"` labels. Extract the `c{nad} custom` DeviceInfo into
`models.py`.

**Acceptance criteria:**
- [ ] The menu shows exactly `add_entity`, `select_edit_entity` and `remove_entity`. Adding, editing and removing a sensor works through them.
- [ ] Existing sensor tests pass with only step ids and index keys changed. Their assertions are unchanged.
- [ ] Regression: an entry with only `"sensor"` options keeps its unique ids and entity ids.

**Verification:**
- [ ] `scripts/test tests/test_config_flow.py tests/test_consistency.py`
- [ ] `scripts/lint`

**Dependencies:** None

**Files likely touched:** `custom_components/hiq/config_flow.py`,
`custom_components/hiq/models.py`, `custom_components/hiq/sensor.py`,
`custom_components/hiq/strings.json`, `translations/en.json`,
`translations/de.json`, `tests/test_config_flow.py`

**Estimated scope:** M

## Task 2: Custom select entities from stored options

**Description:** In `select.async_setup_entry`, create a `HiqSelectEntity` for
each item in `entry.options["select"]`. Each one is created on the custom device
with the stored `unique_id`, uses `name` as its entity name, is enabled by
default and has no entity category.

**Acceptance criteria:**
- [ ] State equals the label of the current PLC value, and `options` keeps the stored order. A value that matches no option gives `unknown`.
- [ ] `select.select_option` writes the mapped integer (negatives included) to `c{nad}.<tag>`.
- [ ] An entry without a `"select"` key sets up without errors and creates no custom selects.

**Verification:**
- [ ] `scripts/test tests/test_select.py` (new)
- [ ] `scripts/lint`

**Dependencies:** None (parallel to T1)

**Files likely touched:** `custom_components/hiq/select.py`,
`custom_components/hiq/models.py`, `tests/test_select.py`

**Estimated scope:** S

## Checkpoint: Foundation
- [ ] `scripts/test` and `scripts/lint` are green
- [ ] Review with the user before continuing

## Task 3: Add custom select via options flow

**Description:** Add `select` to the type choice in `add_entity`, routing to the
new `add_select` step. That step has the tag dropdown (own variables only),
an optional name and a multi-value `label=value` options field. Parse the options
into `{label: int}` and assign a uuid1 unique id.

**Acceptance criteria:**
- [ ] A valid input is stored in `entry.options["select"]`, and after reload the entity exists on the custom device with the right options.
- [ ] Each validation error shows on the form and nothing is stored: `select_options_empty`, `select_option_invalid` (no `=`, non-integer value, empty label), `select_option_duplicate_label` and `select_option_duplicate_value`.
- [ ] The name defaults to the tag. strings.json, en.json and de.json are updated and the consistency test passes.

**Verification:**
- [ ] `scripts/test tests/test_config_flow.py tests/test_consistency.py`
- [ ] `scripts/lint`

**Dependencies:** T1, T2

**Files likely touched:** `custom_components/hiq/config_flow.py`,
`custom_components/hiq/strings.json`, `translations/en.json`,
`translations/de.json`, `tests/test_config_flow.py`

**Estimated scope:** M

## Task 4: Edit custom select

**Description:** `select_edit_entity` lists selects as `"select:<idx>"` /
`"<name> (Select)"` and routes them to `edit_select` (name and options; the tag
stays fixed). The stored options are prefilled as `label=value` strings, and the
same validation as in add applies.

**Acceptance criteria:**
- [ ] The edit form is prefilled with the current name and options.
- [ ] After a change, the entity shows the new name and options and keeps its entity id after reload.
- [ ] Invalid options show the same error keys as in add.

**Verification:**
- [ ] `scripts/test tests/test_config_flow.py tests/test_consistency.py`

**Dependencies:** T3

**Files likely touched:** `custom_components/hiq/config_flow.py`,
`custom_components/hiq/strings.json`, `translations/en.json`,
`translations/de.json`, `tests/test_config_flow.py`

**Estimated scope:** S

## Task 5: Remove custom selects

**Description:** `remove_entity` lists sensors and selects together. Each
removed entry is dropped from its platform list, and its entity is removed from
the registry using that platform's domain.

**Acceptance criteria:**
- [ ] A removed select is gone from both the states and the entity registry.
- [ ] Removing a sensor and a select together leaves the other entries and their indexes intact.

**Verification:**
- [ ] `scripts/test tests/test_config_flow.py`

**Dependencies:** T4

**Files likely touched:** `custom_components/hiq/config_flow.py`,
`tests/test_config_flow.py`

**Estimated scope:** S

## Checkpoint: Flow
- [ ] `scripts/test` and `scripts/lint` are green
- [ ] Manual check: in `scripts/develop`, add, edit, use and remove a custom select
- [ ] Review with the user before continuing

## Task 6: README and final pass

**Description:** Document custom selects in the README next to custom sensors,
including the new menu and the `label=value` format.

**Acceptance criteria:**
- [ ] The README describes adding, editing and removing custom selects, with an example.
- [ ] All SPEC success criteria are checked off.

**Verification:**
- [ ] `scripts/test`, `scripts/lint`, `ruff format --check .`

**Dependencies:** T5

**Files likely touched:** `README.md`

**Estimated scope:** XS

## Checkpoint: Complete
- [ ] All acceptance criteria are met. Coverage of `config_flow.py` and `select.py` has not dropped.
- [ ] Ready for review
