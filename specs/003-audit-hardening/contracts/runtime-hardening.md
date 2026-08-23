# Runtime Hardening Contracts

## Cloud import result

Preview/cycle result retains existing keys and adds `retryable_count` and `quarantined_count`. Only `CloudSnapshotValidationError` increments the latter and moves a file. Other exceptions increment the former and retain the source.

## Quarantine management

- `list_quarantined_snapshots(sync_dir) -> list[dict]`
- `revalidate_quarantined_snapshot(sync_dir, entry_name) -> dict`
- `restore_quarantined_snapshot(sync_dir, entry_name) -> str`
- `delete_quarantined_snapshot(sync_dir, entry_name) -> bool`

All operations accept a single basename and enforce containment under `<sync_dir>/.invalid`. Restore never overwrites an existing snapshot.

## Worker cleanup

Structured cleanup reports whether the QThread actually stopped. Database maintenance starts only when every DB-writing worker reports an actually stopped state. Detaching may remain for shutdown/tab lifecycle but is never maintenance success.

## CSV export

Every user-derived cell is passed through spreadsheet neutralization. Non-dangerous text is unchanged at the CSV reader level; dangerous text receives one leading apostrophe.

## CSV import

Completion returns structured counters. Progress includes the same counters so error/cancel UI can disclose partial commits. A row changes bookmark and note atomically.
