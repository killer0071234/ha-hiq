# Spec: Custom select entities

## Objective

Let users expose any integer PLC tag of their HIQ controller as a Home Assistant
`select` entity, configured in the integration's options flow — the same way
custom sensors work today.

A custom select has a fixed list of options, each mapping a user-defined label
to an integer PLC value (e.g. `off=0`, `eco=1`, `comfort=5`). Choosing an
option writes its value to the tag; the current option is the label whose value
matches the tag's current value.

The options flow is reorganised around a **unified per-type menu**: one
"Add entity", "Edit entity" and "Remove entity" entry, where the user picks the
entity type (sensor / select) when adding, and sees all custom entities of both
types when editing or removing.

### User stories

- As a user, I can add a custom select by picking a tag, a name and a list of
  `label=value` options.
- As a user, I can change the name and options of a custom select later.
- As a user, I can remove custom selects (and sensors) in one step; removed
  entities disappear from the entity registry.
- As an existing user, my configured custom sensors keep working unchanged after
  the update (same storage, same unique ids, same entity ids).

## Assumptions

1. Storage stays per platform in `entry.options`: sensors in
   `entry.options["sensor"]` (unchanged), selects in `entry.options["select"]`.
   No config-entry `VERSION` bump, no migration needed.
2. A stored select looks like:
   ```python
   {
       "tag": "th00_mode",  # without the "cNAD." prefix, like sensors
       "name": "Mode",
       "unique_id": "<uuid1>",
       "options": {"off": 0, "eco": 1, "comfort": 5},
   }
   ```
3. Option labels are shown verbatim (no translation), in the order entered.
4. The tag is read and written as `VarType.INT`, like the existing selects.
5. A PLC value that matches no option gives `current_option = None` (state
   `unknown`), no error.
6. Writing is direct only: `cybro.write_var(tag, value)` followed by
   `coordinator.async_refresh()` — no write-request tag.
7. Custom selects live on the existing `c{nad} custom` device shared with
   custom sensors.
8. Custom selects are enabled by default (unlike the built-in config selects).
   They get no entity category.
9. Option values may be any integer, negative values included (`int()` parse).

## Behaviour

### Options flow

```
init (menu)
├── add_entity            menu: sensor | select
│   ├── add_sensor        existing sensor form (unchanged fields)
│   └── add_select        tag, name, options
├── select_edit_entity    form: pick one entity across both types
│   ├── edit_sensor       existing sensor edit form
│   └── edit_select       name, options
└── remove_entity         form: multi-select across both types
```

- Adding branches through the `add_entity` sub-menu. Editing branches with
  `SchemaFlowFormStep(next_step=<async callable>)`. The callable only receives
  the options, so the platform being edited is kept in a transient
  `_edit_platform` options key, which the edit step removes again.
- Entities in edit/remove lists are keyed `"<platform>:<index>"`
  (e.g. `"sensor:0"`, `"select:2"`) and labelled `"<name> (<Sensor|Select>)"`.
- The options field is a multi-value `SelectSelector` with `custom_value=True`;
  each entry is a `label=value` string. On edit, the stored mapping is shown back
  as `label=value` strings.
- Tag dropdown in `add_select` offers only the controller's own variables
  (same filtering as `get_sensor_setup`). The tag cannot be changed on edit.
- Name defaults to the tag when left empty (same as sensors).

### Validation (errors shown on the form, nothing stored)

| Input | Error key |
|---|---|
| no options | `select_options_empty` |
| entry not of form `label=value` / value not an integer | `select_option_invalid` |
| empty label after stripping | `select_option_invalid` |
| duplicate label | `select_option_duplicate_label` |
| duplicate value | `select_option_duplicate_value` |

Whitespace around label and value is stripped.

### Entity

- Unique id: the stored `unique_id` (uuid1), set when the select is added.
- `options` = labels in stored order; `current_option` from value → label map.
- `extra_state_attributes` = `description` and `variable`, like
  `HiqSelectEntity`.
- Reuse `HiqSelectEntity` (it already takes a label → value mapping and writes
  with `write_var` when `var_write_req` is `None`); only add a name/unique id
  path. No new entity class unless reuse proves impossible.

### Removal

Removing a select also removes its entity from the entity registry
(`SELECT_DOMAIN`), mirroring `validate_remove_sensor`.

## Tech Stack

- Python 3.13+, Home Assistant 2026.9.4, `cybro` 0.4.1
- Tests: `pytest` + `pytest-homeassistant-custom-component` 0.13.367
- Lint/format: `ruff` 0.16.10

## Commands

```
Test:      scripts/test                      # pytest --cov --cov-report=term
Single:    scripts/test tests/test_config_flow.py -k select
Lint:      scripts/lint                      # ruff check . --fix
Format:    ruff format .
Dev HA:    scripts/develop
```

## Project Structure

```
custom_components/hiq/
  config_flow.py        → unified menu, add/edit/remove select steps, validation
  select.py             → set up custom selects from entry.options["select"]
  const.py              → new CONF_* keys if needed (e.g. CONF_ENTITY_TYPE)
  strings.json          → options-flow steps, errors, entity type selector
  translations/en.json  → same as strings.json
  translations/de.json  → German translations
README.md               → "custom select" section next to custom sensors
tests/
  test_config_flow.py   → flow tests (sensor tests adapted to new menu)
  test_select.py        → new: custom select entity state & writes
```

## Code Style

Follow the existing modules: one function per flow step, `handler.options`
mutated directly for sub-items, small helpers instead of duplicated logic.
Example of the expected shape:

```python
async def validate_select_setup(
    handler: SchemaCommonFlowHandler, user_input: dict[str, Any]
) -> dict[str, Any]:
    """Validate select input."""
    user_input[CONF_OPTIONS] = _parse_select_options(user_input[CONF_OPTIONS])
    user_input[CONF_UNIQUE_ID] = str(uuid.uuid1())

    # Default name is tag name
    if user_input.get(CONF_NAME) is None:
        user_input[CONF_NAME] = user_input[CONF_TAG]

    selects: list[dict[str, Any]] = handler.options.setdefault(SELECT_DOMAIN, [])
    selects.append(user_input)
    return {}
```

- One import per line (existing ruff isort style), docstring on every function.
- Raise `SchemaFlowError("<error_key>")` for validation errors.
- Use HA constants (`CONF_NAME`, `CONF_OPTIONS`, `CONF_UNIQUE_ID`,
  `SELECT_DOMAIN`, `SENSOR_DOMAIN`) instead of string literals.

## Testing Strategy

Tests use the existing `init_integration` fixture and `fake_controller`.
Write the tests first (TDD), and keep coverage of `config_flow.py` and `select.py`
at its current level or higher.

`tests/test_config_flow.py`:
- add select → entity exists on custom device, options/labels correct
- edit select → name and options change, entity id unchanged after reload
- remove select (and mixed sensor+select removal) → gone from states and registry
- each validation error from the table above
- add-entity type step routes to `add_sensor` / `add_select`
- existing sensor tests adapted to the new menu step ids, same assertions

`tests/test_select.py`:
- `current_option` reflects the PLC value; unmapped value → `unknown`
- `select.select_option` calls `write_var(tag, value)` with the mapped integer
- options-entry without `"select"` key → no custom selects, no error

Regression: an entry created with the old options format (only `"sensor"`)
loads with unchanged sensor unique ids and entity ids.

## Boundaries

- **Always:** run `scripts/test` and `scripts/lint` before committing; keep
  `strings.json`, `en.json` and `de.json` in sync; update README.
- **Ask first:** bumping the config-entry `VERSION` or changing the stored
  sensor format; adding dependencies; changing behaviour of the built-in
  (auto-discovered) selects; a dedicated new entity class instead of reusing
  `HiqSelectEntity`.
- **Never:** change unique ids or entity ids of existing custom sensors; drop or
  weaken existing tests to make the menu refactor pass; write to the PLC during
  the options flow.

## Success Criteria

1. A custom select can be added, edited and removed through the options flow,
   and changes take effect after the entry reloads.
2. Selecting an option writes the mapped integer to `cNAD.<tag>`. The state
   follows the PLC value on the next poll.
3. All validation errors in the table appear and nothing is stored when they do.
4. Existing custom sensors survive the update untouched (regression test passes).
5. The options menu shows exactly three entries: add, edit and remove entity.
   Edit and remove list both sensors and selects.
6. `scripts/test` and `scripts/lint` pass, and coverage of the touched modules
   does not drop.

## Resolved Decisions

1. Menu step ids are renamed (`add_sensor` → `add_entity` etc.); nothing stored
   depends on them.
2. Custom selects are always enabled by default and have no entity category
   (not diagnostic, not config).
3. Option values may be any whole number, negative included.
