# Tasks: Improve README and help texts

Spec: [SPEC.md](../SPEC.md) · Plan: [plan.md](plan.md)

## Phase 1: Foundation and UI texts

- [x] **Task 1: Plain-text strings.json + guard tests**
  - Description: Replace every `[%key:component::hiq::…%]` and every
    non-existent `common::` ref in `strings.json` with the text from
    `en.json`, so both files say the same. Add the guard tests.
  - Acceptance:
    - `strings.json` contains no `component::hiq` refs, and every remaining
      `[%key%]` is on the allow-list (see plan).
    - New test: `strings.json` equals `en.json` (allowed refs resolved).
    - New test: no `component::hiq` refs, refs only from the allow-list.
  - Verify: `scripts/test tests/test_consistency.py`, then `scripts/test`
  - Files: `strings.json`, `translations/en.json`, `tests/test_consistency.py`
  - Dependencies: none · Scope: S

- [x] **Task 2: Config flow and options flow help texts**
  - Description: Setup step description (scgi server prerequisite, README
    link), labels and `data_description` with examples for host/port/address,
    clearer `cannot_connect` / `plc_not_existing`. Titles/descriptions for the
    options menus `init`, `add_entity`, `select_edit_entity`, `remove_entity`.
    Separate add/edit descriptions, a `data_description` for every field, typo
    fixes ("to to").
  - Acceptance:
    - Every `config.step.*` and `options.step.*` has a `description`, and every
      `data` key has a `data_description`, in en + de.
    - New test for the point above.
    - `edit_sensor`/`edit_select` descriptions say "edit", not "add".
  - Verify: `scripts/test tests/test_consistency.py tests/test_config_flow.py`
  - Files: `strings.json`, `translations/en.json`, `translations/de.json`,
    `tests/test_consistency.py`
  - Dependencies: Task 1 · Scope: M

- [x] **Task 3: Entity name typo fixes**
  - Description: Fix spelling/casing in `entity.*.name` (e.g. "temperatur",
    "Auxilary", "Iex voltage") in en, and the same plus umlauts in de.
    Translation keys stay the same.
  - Acceptance:
    - No known typos remain. The list of changed names is written down for
      the PR / release notes.
    - Entity-id assertions in tests updated only where the slug really
      changes.
  - Verify: `scripts/test`
  - Files: `strings.json`, `translations/en.json`, `translations/de.json`,
    possibly `tests/test_sensor.py` / `tests/test_entities.py`
  - Dependencies: Task 1 · Scope: S

### Checkpoint 1
- Renamed names (for release notes):
  - en: Iex/iex voltage → IEX voltage; Auxilary → Auxiliary (sensor + switch);
    Max temperatur external → Max temperature external;
    {module} General error → {module} general error;
    Operation mode hvac → Operation mode HVAC.
  - de: Hystherese → Hysterese (3x); Versorgungpannung → Versorgungsspannung;
    aktvieren → aktivieren; Aussen- → Außen- (2x); Interer → Interner Sensor;
    Zykluszeit maximum → Zykluszeit Maximum; IP Adresse → IP-Adresse.
  - New installs only: `…_auxilary_temperature` → `…_auxiliary_temperature`,
    `…_max_temperatur_external` → `…_max_temperature_external`.
- [x] `scripts/test` and `scripts/lint` pass
- [x] `scripts/develop`: setup and all options steps read well in en + de
- [x] Human review

## Phase 2: Services and metadata

- [x] **Task 4: Service texts, translations and wider write_tag selector**
  - Description: Unique names (`alarm_event` → "Alarm event"), consistent
    descriptions in `services.yaml`. Explain that `tag` takes the variable
    without the `cNAD.` prefix. `write_tag.value` selector → number, box,
    `step: any`, -2147483648..2147483647. Add a `services` section to
    strings/en/de.
  - Acceptance:
    - All 7 services have name + description and field name + description in
      en + de. Names are unique (test).
    - Test: selector range and `step: any`.
    - Test: `write_tag` with `value: -5` writes `-5` to `c1000.<tag>` on the
      fake controller.
  - Verify: `scripts/test tests/test_consistency.py tests/test_services.py`
  - Files: `services.yaml`, `strings.json`, `translations/en.json`,
    `translations/de.json`, `tests/test_consistency.py`,
    `tests/test_services.py`
  - Dependencies: Task 1 · Scope: M

- [x] **Task 5: iot_class local_polling**
  - Description: `manifest.json` `iot_class` → `local_polling`, no version
    bump.
  - Acceptance: test asserts `iot_class == "local_polling"`.
  - Verify: `scripts/test tests/test_consistency.py`
  - Files: `manifest.json`, `tests/test_consistency.py`
  - Dependencies: none · Scope: XS

### Checkpoint 2
- [x] `scripts/test` and `scripts/lint` pass
- [ ] Developer tools → Actions: all services with correct texts (en + de),
      `write_tag` accepts `-5`, `100000`, `1.5`
- [ ] Human review

## Phase 3: Documentation

- [ ] **Task 6: docs/entities.md**
  - Description: Full entity reference, one section per platform. Columns:
    Name | Description | Controller variable | Enabled by default. Names come
    from `en.json`, and enabled flags come from `entity_registry_enabled_default`
    in the code. Includes the custom sensor / custom select details from the
    README.
  - Acceptance:
    - Every English entity name created by `init_integration` appears (test).
    - No entity listed that the code cannot create (manual check against
      `translation_key`s, recorded in the PR).
  - Verify: `scripts/test tests/test_consistency.py`
  - Files: `docs/entities.md`, `tests/test_consistency.py`
  - Dependencies: Task 3 · Scope: M

- [ ] **Task 7: README restructure**
  - Description: Sections Prerequisites, Installation (HACS + manual, current
    menu names), Configuration (setup fields, options flow, polling
    5 s / 10 s), Entities (overview + absolute link to `docs/entities.md`),
    Devices (keep), Services (all 7, fields, YAML examples for `write_tag` and
    `precede_event`), Troubleshooting (link to DEBUGGING.md), Removal, Tested
    devices, Contributing, Credits. Keep `{% if not installed %}`, remove
    `exampleimg`.
  - Acceptance:
    - Every registered service is mentioned in the README (test).
    - All listed sections are there, and no entity tables remain in the README.
    - Every link reference used is defined, and every defined one is used.
  - Verify: `scripts/test tests/test_consistency.py`, preview the Markdown
  - Files: `README.md`, `tests/test_consistency.py`
  - Dependencies: Tasks 4, 6 · Scope: S

### Checkpoint: Complete
- [ ] All spec success criteria checked
- [ ] `scripts/test` and `scripts/lint` pass
- [ ] Human review before PR
