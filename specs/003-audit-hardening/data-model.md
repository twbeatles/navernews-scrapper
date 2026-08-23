# Data Model: 감사 후속 안정성 강화

## CloudSnapshotValidationError

- Base: `CloudSyncError`
- Meaning: snapshot bytes, manifest, archive member, size/path policy, extracted SQLite integrity가 계약을 위반함
- Rule: DB preview/merge, local lock, permission, disk, cancellation 오류에는 사용하지 않음

## QuarantineEntry

- `path`: `.invalid` 안의 containment 검증된 절대 경로
- `original_name`, `reason`, `quarantined_at`, `metadata_path`
- `validation_status`: `unknown | valid | invalid`
- Transitions: `quarantined → revalidated(valid) → restored`, `quarantined → deleted`

## WorkerCleanupOutcome

- `state`: `finished | already_finished | detached_running | failed`
- `safe_for_database_maintenance`: 앞의 두 실제 종료 상태만 true
- Compatibility: 기존 bool cleanup은 기존 UI cleanup 의미를 유지

## CsvArticleStateMutationResult

- `status`: `updated | unchanged | missing`
- `bookmark_changed`, `note_changed`: bool
- Rule: 한 link의 mutation은 단일 transaction

## CsvImportResult

- `processed`, `updated`, `unchanged`, `missing`, `failed`, `truncated_notes`, `last_row`
- Invariant: `processed == updated + unchanged + missing + failed`

## Dependency Contract

- `requirements.txt`: runtime direct dependencies
- `requirements-build.txt`: runtime + build/test tools
- Release environment: Windows, Python 3.14
- Validation: install input + QtNetwork/entrypoint smoke + tests
