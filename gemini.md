# Gemini Assistant Guide - 뉴스 스크래퍼 Pro

이 문서는 현재 저장소 상태를 빠르게 파악하기 위한 AI assistant용 요약입니다. 오래된 addendum과 날짜별 작업 로그는 제거했습니다.

## Project Snapshot

- App: Naver News tab search/management desktop tool
- Runtime: Python 3.14, PyQt6, SQLite, requests
- News API: **NAVER API HUB** (not legacy Developers Center)
- Entry point: `news_scraper_pro.py`
- Bootstrap: `core.bootstrap.main()`
- UI facade: `ui.main_window.MainApp`
- DB facade: `core.database.DatabaseManager`
- API helpers: `core.naver_api`
- Packaging: `news_scraper_pro.spec` / PyInstaller onefile
- Version: `core.constants.VERSION`

## Architecture

```text
core/
  naver_api.py             # API HUB URL, auth headers, error parsing
  database.py              # DatabaseManager composition root
  db_schema_support/       # schema and migration helpers
  db_queries_support/      # fetch/count/archive/search queries
  db_mutations_support/    # upsert/state/tag/maintenance writes
  workers_support/         # ApiWorker, DBWorker, job workers
  cloud_sync_support/      # ZIP snapshot I/O and import flow
  backup_support/          # backup/restore implementation
  runtime_support/         # DATA_DIR and legacy migration
ui/
  main_window.py           # MainApp facade
  main_window_support/     # shell/config/badge/tray/maintenance
  main_window_fetch_support/
  main_window_io_support/
  news_tab.py              # NewsTab facade
  news_tab_support/
  dialogs_support/
tests/
```

Root modules such as `database_manager.py`, `query_parser.py`, `workers.py`, and `styles.py` are compatibility wrappers.

## NAVER API HUB

- Endpoint: `GET https://naverapihub.apigw.ntruss.com/search/v1/news`
- Headers: `X-NCP-APIGW-API-KEY-ID`, `X-NCP-APIGW-API-KEY`
- Shared helpers live in `core/naver_api.py` and must be used by both `ApiWorker` and settings validation.
- Do **not** restore legacy `openapi.naver.com` or `X-Naver-Client-*` headers.
- Config still stores `client_id` / `client_secret` field names; values must be API HUB credentials.
- Parse both Search flat errors and API Gateway nested `error` objects via `parse_naver_api_error`.
- Map HTTP 401/403 to `auth_error` for UI messaging.

## Important Contracts

- Query scope uses canonical fetch keys from `core.query_parser`.
- `upsert_news(...) -> tuple[int, int]` remains compatible.
- `upsert_news_detailed(...) -> NewsUpsertResult` is the preferred fetch save path.
- `count_news(...) -> int` remains compatible.
- `count_news_states(...) -> NewsCountSummary` is the preferred full reload count path.
- `ApiWorker.finished` keeps the existing payload keys.
- `DBWorker` full reload calculates total/unread together; append reuses known total.
- FTS schema/backfill exists, but LIKE token-AND remains the search truth.
- Cloud sync exchanges ZIP snapshots, not live cloud-hosted SQLite files.

## Change Guide

| Change | Start Here |
|---|---|
| API endpoint/headers/errors | `core/naver_api.py`, `core/workers_support/api_worker.py` |
| Settings API validation/UI copy | `ui/_settings_dialog_tasks.py`, `ui/_settings_dialog_content.py`, `ui/_settings_dialog_docs.py` |
| Fetch/API behavior | `core/workers_support/api_worker.py` |
| Upsert performance | `core/db_mutations_support/news_upsert.py` |
| List/count semantics | `core/db_queries_support/fetch.py` |
| News tab load/render | `ui/news_tab_support/` |
| Badge/tray counts | `ui/main_window_support/ui_shell_support/` |
| Settings import/export | `ui/main_window_io_support/` |
| Cloud merge | `core/cloud_sync_support/`, `core/db_cloud_sync_support/` |
| Backup/restore | `core/backup_support/`, `ui/dialogs_support/backup_dialog/` |
| Packaging | `news_scraper_pro.spec` |

## Validation

```bash
python -m pytest -q
python -m pyright
```

For document/spec changes:

```bash
python -m pytest tests/test_encoding_smoke.py tests/test_version_history_guard.py tests/test_spec_runtime_tmpdir.py -q
```

For API HUB regression:

```bash
python -m pytest tests/test_naver_api_hub.py tests/test_settings_validation_http_policy.py -q
```

For packaged release checks:

```bash
python -m PyInstaller --noconfirm --clean news_scraper_pro.spec
```

## Repository Hygiene

- Do not commit runtime DB/config/log files, build output, caches, `.codegraph/`, or local scratch folders.
- Keep Markdown concise and current-state oriented.
- Keep `news_scraper_pro.spec` focused on the actual dependency and packaging contract.
- Preserve UTF-8 text files.
- When bumping `VERSION`, add a matching `## v{VERSION}` section to `update_history.md`.
