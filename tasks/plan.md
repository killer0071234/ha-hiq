# Implementation Plan: Improve README and help texts

Spec: [SPEC.md](../SPEC.md) · Tasks: [todo.md](todo.md)

## Overview

Make the UI texts and documentation correct and complete. `strings.json` becomes
plain English text with `en.json` as an exact copy. Setup and options dialogs
and services get full help texts in English and German. Entity name typos are
fixed. The `write_tag` value selector is widened and `iot_class` is corrected.
The README is restructured, and the entity reference moves to
`docs/entities.md`. Python code is not changed. Only tests are added.

## Architecture Decisions

- **Guard tests first.** Task 1 adds the consistency tests (`strings.json` ==
  `en.json`, no `component::hiq` refs) together with the conversion, so every
  later text edit is checked automatically.
- **Translation files are edited together.** Every task that touches texts
  edits `strings.json`, `en.json` and `de.json` in the same commit, so
  `test_strings_match_english` and `test_translation_complete` stay green
  after every task.
- **Text slices by area** (config flow, options flow, entities, services)
  instead of by file. Each slice can be reviewed in the UI on its own.
- **Docs last.** `docs/entities.md` and the README use the final entity names
  and service texts, so they are written after the texts are settled.
- **No `[%key%]` refs (decided in Task 1):** custom integrations don't
  resolve them, so `strings.json` is plain text and equals `en.json`.
  `test_strings_equal_english` and `test_translation_has_no_references` keep
  it that way.

## Task List

### Phase 1: Foundation and UI texts
- [x] Task 1: Plain-text strings.json + guard tests
- [x] Task 2: Config flow and options flow help texts
- [x] Task 3: Entity name typo fixes

### Checkpoint 1
- [x] `scripts/test` and `scripts/lint` pass
- [x] Dialogs reviewed in the UI (en + de) via `scripts/develop`

### Phase 2: Services and metadata
- [x] Task 4: Service texts, translations and wider write_tag selector
- [x] Task 5: iot_class local_polling

### Checkpoint 2
- [x] `scripts/test` and `scripts/lint` pass
- [ ] Services shown correctly in Developer tools → Actions (en + de)

### Phase 3: Documentation
- [ ] Task 6: docs/entities.md
- [ ] Task 7: README restructure

### Checkpoint: Complete
- [ ] All spec success criteria checked
- [ ] Review with human before PR

## Risks and Mitigations

| Risk | Impact | Mitigation |
|---|---|---|
| Fixing a name typo changes the entity_id for **new** installs (e.g. `…_auxilary_temperature` → `…_auxiliary_temperature`) | Med | Existing installs keep IDs (registry). Mention in release notes. Check `tests/test_entities.py` / `test_sensor.py` entity ids. |
| Services `services` translations override `services.yaml` texts | Low | Keep both identical in English, check in Developer tools. |
| Number selector with `step: any` and ±2^31 bounds renders badly | Low | Check in UI at Checkpoint 2. Fallback: `step: 1` + text hint for decimals. |
| `docs/entities.md` drifts again | Med | Substring test against entities created by `init_integration`. |
| The fake controller doesn't create every entity (e.g. EnOcean, power meter phases) | Med | Check the fixture's entity list in Task 6. Document entities that aren't covered by hand, and list them in the PR. |
| HACS renders README outside the repo, relative links break | Low | Absolute GitHub URLs for `docs/entities.md` and `DEBUGGING.md`. |

## Open Questions

None.
