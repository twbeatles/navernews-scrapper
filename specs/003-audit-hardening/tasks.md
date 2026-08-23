# Tasks: 감사 후속 안정성 강화

**Input**: `spec.md`, `plan.md`, `research.md`, `data-model.md`, `contracts/`

## Phase 1: Foundation

- [x] T001 Add failing focused regression tests for cloud, maintenance, and CSV behavior in `tests/`
- [x] T002 Define shared structured cloud/worker/CSV result contracts without breaking facades

## Phase 2: User Story 1 — Reliable cloud sync (P1)

**Independent Test**: a valid snapshot survives a transient preview/merge failure; malformed snapshots are quarantined; a quarantined valid entry can be restored without overwrite.

- [x] T003 [US1] Add snapshot validation error classification in `core/cloud_sync_support/models.py` and `snapshot_io.py`
- [x] T004 [US1] Preserve transient failures and report retryable/quarantined counts in `core/cloud_sync_support/import_flow.py` and `ui/main_window_io_support/cloud.py`
- [x] T005 [US1] Add contained quarantine list/revalidate/restore/delete APIs in `core/cloud_sync_support/snapshot_io.py` and facades
- [x] T006 [US1] Add quarantine management UI reachable from cloud settings
- [x] T007 [US1] Pass cloud sync regression tests including selection, preview, automatic cycle, and manual import

## Phase 3: User Story 2 — Exclusive database maintenance (P1)

**Independent Test**: maintenance is refused while a detached but running DB-writing fetch exists and succeeds after actual thread completion.

- [x] T008 [US2] Add structured cleanup outcome while retaining `cleanup_worker() -> bool` compatibility
- [x] T009 [US2] Require actual worker termination in `ui/main_window_support/base_support/maintenance.py`
- [x] T010 [US2] Replace the former force-detach-success expectation with blocking and post-finish regression tests

## Phase 4: User Story 3 — Safe and explainable data transfer (P1)

**Independent Test**: dangerous CSV prefixes are neutralized and import result totals remain exact after success, row failure, and cancellation.

- [x] T011 [US3] Add spreadsheet-safe CSV cell encoding in `ui/main_window_io_support/exports.py`
- [x] T012 [US3] Add atomic per-link bookmark/note import mutation to the database facade and mutation support
- [x] T013 [US3] Return and report processed/updated/unchanged/missing/failed/truncated/last-row counters
- [x] T014 [US3] Preserve latest progress result in UI and disclose partial commits on error/cancel
- [x] T015 [US3] Pass CSV formula, atomicity, totals, partial failure, and cancellation tests

## Phase 5: User Story 4 — Reproducible runtime and accurate docs (P2)

**Independent Test**: dependency contract drives CI installation, QtNetwork/entrypoint smoke is present, and documented runtime/spec paths match constants and feature pointer.

- [x] T016 [US4] Add runtime/build dependency contracts and use them from `.github/workflows/release.yml`
- [x] T017 [US4] Add dependency/import smoke workflow and tests
- [x] T018 [US4] Correct README runtime filenames and CLAUDE/AGENTS active feature references and filename case
- [x] T019 [US4] Bump `core.constants.VERSION` and add matching `update_history.md` entry

## Phase 6: Validation and audit closure

- [x] T020 Run focused pytest suites and pyright
- [x] T021 Run the full pytest suite and document environment-only failures honestly
- [x] T022 Run PyInstaller/package smoke where the local environment permits
- [x] T023 Update `PROJECT_AUDIT.md` with remediation status and remaining external limitations
- [x] T024 Re-check every completed task and leave no unchecked implementation item without an explicit reason

## Dependencies & Execution Order

- T001 precedes implementation so regressions are observable.
- T003–T007, T008–T010, and T011–T015 are independently testable after T002.
- T016–T019 follow functional changes so dependency/docs/version describe the delivered state.
- T020–T024 require all selected implementation tasks.

## Implementation Strategy

Implement P1 stories in audit risk order: cloud data preservation, maintenance exclusion, CSV safety/atomicity. Validate each focused suite before proceeding. Finish with P2 dependency/document consistency and whole-repository regression.
