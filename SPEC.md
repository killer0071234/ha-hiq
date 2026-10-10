# Spec: Improve README and help texts

## Objective

Users set up and use the HIQ integration through the Home Assistant UI and the
README. Both are out of date and partly wrong:

- `strings.json` refers to keys that do not exist
  (`[%key:component::hiq::config::step::sensor::...%]`,
  `common::config_flow::error::plc_not_existing`,
  `common::config_flow::data::address`). The real texts only live in
  `translations/en.json`, so the two files have drifted.
- The options flow menus have no title or description, and `edit_sensor` says
  "Add a custom sensor…".
- Services have no translations, `alarm_event` is named "Home event" (same as
  `home_event`), and the descriptions are inconsistent ("HIQ - controller").
- Entity names have typos ("Max temperatur external", "Auxilary",
  "Iex voltage").
- The README entity tables list names the integration does not create (e.g.
  `thermostat setpoint idle`, `hystheresis`). Per-phase power meter sensors,
  setpoint min/max, the fan limit select, EnOcean and `alarm_event` are
  missing. Installation and "disable new entities" steps use old HA menu
  names. There is no troubleshooting section and no section on removing the
  integration.

Also, `manifest.json` declares `iot_class: local_push` although the integration
polls, and the `write_tag` UI selector only allows values 0–1000, although
controller variables are 16/32-bit integers or reals.

This change fixes texts, documentation and these two metadata/UI limits. The
service handlers, entities and polling are unchanged.

### User stories

- As a new user, I can install the scgi server and the integration, and set up
  a controller, using only the README and the texts in the setup dialog.
- As a user, every field in the setup and options dialogs explains what to
  enter, with an example.
- As a user, I can find any entity the integration created in the README by its
  displayed name, and see what it does and whether it is enabled by default.
- As a German user, services, dialogs and entity names are shown in German.
- As a user with a problem, the README tells me the common causes (scgi server
  not running, wrong NAD, module `general_error`) and how to get debug logs.

## Decisions (approved)

1. **Scope: texts + README + two small fixes.** `strings.json`,
   `translations/en.json`, `translations/de.json`, `services.yaml`,
   `manifest.json`, `README.md` and a new `docs/entities.md`. No change to the
   Python code.
   - `manifest.json`: `iot_class` → `local_polling`.
   - `write_tag` `value` selector widened (see Services). The service schema
     (`cv.string`) already accepts any value, so only the UI limit changes.
   - Entity tables move from the README to `docs/entities.md`.
2. **`strings.json` holds plain English text.** `translations/en.json` is an
   identical copy. The only `[%key:...%]` references kept are ones that point
   to keys HA itself provides (`common::...`, `state::default::off`,
   `component::sensor::entity_component::<x>::name`) and that resolve to the
   intended text. Every reference into `component::hiq::...` is replaced by
   text.
3. **Entity names: typo, spelling and casing fixes only.** For example
   "Max temperatur external" → "Max temperature external", "Auxilary" →
   "Auxiliary", "Iex voltage" → "IEX voltage". Translation keys stay the same
   (`auxilary_temperature` etc.), so `unique_id`s and entity IDs don't change.
   Only the friendly names of entities that use the default name change.
4. **The existing SPEC.md is replaced.** The module device info spec is in git
   history (0.5.0).

## Scope of changes

### Config flow (`config.*`)

- `step.user`: description says an scgi server must be running and links to
  the README. Fields `host`, `port`, `address` get a label and a
  `data_description` with an example (add-on host `85493909-cybroscgiserver`,
  port `4000`, NAD e.g. `1000`).
- `error.cannot_connect` / `error.plc_not_existing`: say what to check.
- `abort.already_configured`: plain text.

### Options flow (`options.*`)

- `init` and `add_entity` menus get a `title` and a `description`.
- `add_sensor`, `edit_sensor`, `add_select`, `edit_select`: each has a title, a
  description that matches the step (edit ≠ add), and a `data_description` for
  every field, with an example where it helps (`tag`, `value_template`,
  `options`).
- `select_edit_entity`, `remove_entity`: add a description.
- Fix "to to read" and similar typos.

### Services

- `services.yaml`: `alarm_event` gets its own name ("Alarm event").
  Descriptions use one consistent pattern: "Sends the smartphone … event to the
  HIQ controller." `write_tag` explains that `tag` is the variable name
  without the `cNAD.` prefix (the integration adds `c<NAD>.` for each targeted
  controller, see `_get_tag_list`).
- `write_tag` `value` selector: `number`, `mode: box`, `step: any`,
  `min: -2147483648`, `max: 2147483647` (32-bit signed, CyBro `long`; `real`
  values are allowed through `step: any`). The example stays `10`.
- New `services` section in `strings.json`, `en.json` and `de.json` with
  `name`, `description` and `fields.<field>.name/description` for all 7
  services.

### Entity names (`entity.*`)

- Fix typos and casing in English names. German names are checked for the same
  issues and for missing umlauts.

### README.md

Restructure into:

1. Intro: what the integration does and which hardware it supports.
2. **Prerequisites**: CybroScgiServer (add-on recommended, Docker, native).
3. **Installation**: HACS (my.home-assistant badge), manual. Steps use
   current HA menu names (Settings → Devices & services → Add integration).
4. **Configuration**: a table of the setup fields with examples, the options
   flow (custom sensor, custom select) and polling interval (5 s for the
   add-on, 10 s otherwise).
5. **Entities (overview)**: supported platforms and HIQ modules (light,
   cover, climate, …) with a short note per platform and a link to
   `docs/entities.md` for the full list.
6. **Devices**: keep the current module card id / firmware section.
7. **Services**: all 7, with fields and a YAML example for `write_tag` and
   `precede_event`.
8. **Troubleshooting**: cannot connect, controller not found, missing entities
   (`general_error`, disabled by default), enabling debug logging (link to
   DEBUGGING.md).
9. **Removing the integration**.
10. Tested devices, contributing, credits.

Keep the `{% if not installed %}` HACS template block and all link references.
Remove unused link references (`exampleimg`). Use absolute GitHub URLs for
links to `docs/entities.md` and `DEBUGGING.md`, because HACS renders the README
outside the repository.

### docs/entities.md (new)

One section per platform. Each table lists the **displayed name** (as in
`en.json`), the description, the controller variable and whether it is
enabled by default. The tables are checked against the code
(`translation_key`, `entity_registry_enabled_default`), so every entity the
integration creates is listed and no extra ones are. It also contains the
custom sensor / custom select details currently in the README.

### manifest.json

- `iot_class`: `local_push` → `local_polling`. No version bump in this change.

## Tech Stack

Home Assistant custom integration (Python 3.13). Translations are HA JSON
translation files, the README is Markdown rendered by GitHub and HACS. No new
dependencies.

## Commands

```bash
Test:      scripts/test                     # pytest --cov
Test one:  scripts/test tests/test_consistency.py
Lint:      scripts/lint                     # ruff check . --fix
JSON:      python -m json.tool custom_components/hiq/strings.json > /dev/null
Dev HA:    scripts/develop                  # manual check of dialogs in the UI
```

## Project Structure

```
custom_components/hiq/strings.json        → source English texts (plain text)
custom_components/hiq/translations/en.json → identical copy of strings.json
custom_components/hiq/translations/de.json → German, same keys as en.json
custom_components/hiq/services.yaml       → service schema + English fallback texts
custom_components/hiq/manifest.json       → iot_class only
README.md                                 → user documentation (GitHub + HACS)
docs/entities.md                          → full entity reference (new)
DEBUGGING.md                              → linked from README troubleshooting
tests/test_consistency.py                 → translation / docs consistency tests
```

## Code Style

JSON: 2-space indent, keys in the existing order, no trailing commas. Texts
use sentence case, no trailing period on names/labels, full sentences with a
period in descriptions. Examples start with "e.g." (English) and "z. B."
(German). Write "HIQ controller" (not "HIQ - controller"), "scgi server",
"NAD".

```json
"services": {
  "write_tag": {
    "name": "Write tag",
    "description": "Writes a value to a variable of the HIQ controller.",
    "fields": {
      "tag": {
        "name": "Variable",
        "description": "Name of the controller variable, e.g. smartphone_presence_signal."
      },
      "value": {
        "name": "Value",
        "description": "Value to write, e.g. 10. Negative and decimal values are allowed."
      }
    }
  }
}
```

README tables use the column order
`| Name | Description | Controller variable | Enabled by default |`.
Controller variables are written as `cNAD.thYY_setpoint_idle` (`NAD` =
controller address, `YY` = module number). Names are shown as they appear in
HA (`Setpoint eco`), not as variable names.

## Testing Strategy

pytest with `pytest-homeassistant-custom-component`. Extend
`tests/test_consistency.py`:

- `strings.json` and `en.json` are **equal**, not only the same keys.
- `strings.json` has no `[%key:component::hiq::` references, and every other
  `[%key:...%]` is in an allow-list of HA keys.
- `de.json` contains `services.*` (extend `test_translation_complete` with the
  `services.` prefix).
- Every service in `services.yaml` has `name` + `description`, and every field
  has `name` + `description`, in `en.json` and `de.json`.
- Every service name is unique.
- The README mentions every registered service, and `docs/entities.md`
  mentions every English entity name that is created in the
  `init_integration` fixture (simple substring check).
- The `write_tag` `value` selector in `services.yaml` allows at least
  -2147483648..2147483647 and decimal steps.
- A `write_tag` call with a negative value (e.g. `-5`) writes `-5` to
  `c1000.<tag>` on the fake controller.
- `manifest.json` `iot_class` is `local_polling`.

The existing tests must keep passing. Manual check: run `scripts/develop`, go
through setup and all options-flow steps in English and German.

## Boundaries

- **Always:** keep `en.json` an exact copy of `strings.json`. Add every new key
  to `de.json`. Check each README entity row against the code. Run
  `scripts/test` and `scripts/lint` before each commit.
- **Ask first:** renaming translation keys or service ids, changing service
  schemas or limits beyond the `write_tag` selector, any other
  `manifest.json` change (version, requirements), adding languages, adding
  images or screenshots.
- **Never:** change entity `unique_id`s, service handlers or polling, remove the
  `{% if not installed %}` block, delete or skip existing tests, add new
  dependencies.

## Success Criteria

- [ ] `strings.json` == `translations/en.json` (byte-identical after
      `json.load`), no `component::hiq` references.
- [ ] Every config/options step has a description, and every input field has a
      `data_description`.
- [ ] All 7 services have unique names and translated texts in en + de.
- [ ] No known typos remain in entity names (list in the PR).
- [ ] Every entity created by the test fixture appears in `docs/entities.md`
      under its displayed name, and the file lists no entity that doesn't
      exist. Every service appears in the README.
- [ ] README has Prerequisites, Installation, Configuration, Entities
      (overview + link), Devices, Services, Troubleshooting and Removal
      sections, with current HA menu names.
- [ ] `write_tag` accepts negative, large and decimal values in the UI.
- [ ] `manifest.json` `iot_class` is `local_polling`.
- [ ] `scripts/test` and `scripts/lint` pass.

## Open Questions

None. Resolved: `iot_class` → `local_polling` (in this change), widen the
`write_tag` selector (in this change), move the entity tables to
`docs/entities.md`.
