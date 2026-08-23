# Project Audit

감사 기준: 2026-08-23, commit `7be932a`

후속 구현 기준: 2026-08-23, version `32.8.0`. 아래 본문은 발견 당시의 근거를 보존하며, 각 이슈/갭의 현재 상태는 이 후속 기록과 항목 제목에 표시한다.

### Remediation Status

- **ISSUE-001 Resolved:** `CloudSnapshotValidationError`만 격리하고 DB/IO/예상 밖 병합 오류는 `retryable_count`로 보고하면서 원본을 보존한다. 격리 목록·재검증·복구·삭제 API/UI도 추가했다.
- **ISSUE-002 Resolved:** maintenance 경로에서 force detach를 제거하고 worker가 실제 종료되지 않으면 작업 시작을 거부한다.
- **ISSUE-003 Resolved:** 모든 사용자 유래 CSV cell에 선행 whitespace/control까지 고려한 spreadsheet formula 중화를 적용했다.
- **GAP-001 Resolved:** bookmark/note를 기사 단위 transaction으로 처리하고 updated/unchanged/missing/failed/last-row 및 취소·오류 전 부분 결과를 보고한다.
- **GAP-002 Resolved:** `requirements.txt`, `requirements-build.txt`, Windows/Python 3.14 quality workflow, QtNetwork/entrypoint smoke를 추가했다.
- **GAP-004 Resolved:** 설정의 클라우드 동기화 영역에서 격리 관리에 접근할 수 있다.
- **Remaining limitation:** 실제 NAVER API HUB credential, 실제 cloud-drive 동시성, EXE UI 자동조작 E2E는 외부 환경이 없어 실행하지 않았다. 로컬 전체 pytest는 기존 전역 site-packages의 간헐적 QtNetwork DLL 충돌로 collection이 중단됐으나, 관련 없는 전체 범위는 333 passed/10 subtests, 변경 집중 범위는 48 passed/5 subtests, pyright는 0 errors, PyInstaller build는 성공했다.

## 1. Executive Summary

이 프로젝트는 NAVER API HUB 뉴스 검색 결과를 탭별로 수집하고 로컬 SQLite에 보존하는 Windows용 PyQt6 데스크톱 앱이다. 검색·필터·읽음·북마크·메모·태그·자동화·내보내기·백업·클라우드 동기화·서명 업데이트까지 기능 범위가 넓으며, 최근 안정화 코드와 회귀 테스트가 상당히 촘촘하게 들어가 있다.

- **전체 상태:** 핵심 데이터 계층과 네트워크 실패 처리는 대체로 건전하다. SQLite 트랜잭션, WAL, 원자적 설정 저장, 백업 자체 검증·복원 롤백, worker stale-result 차단, API timeout/retry/cooldown, 업데이트 서명·해시 검증이 확인됐다.
- **전체 위험도:** **Medium**. 이번 감사에서 Critical 또는 High 심각도의 확정 결함은 찾지 못했다. 다만 실제 production 경로에 도달하는 Medium 이슈 3개가 남아 있다.
- **가장 중요한 문제:**
  1. 클라우드 스냅샷 병합/미리보기의 모든 예외를 스냅샷 손상으로 취급해, 일시적 DB 오류에도 정상 ZIP을 `.invalid`로 이동한다.
  2. 유지보수 진입 시 timeout 난 fetch worker를 “강제 분리 성공”으로 간주해 실제 thread가 끝나기 전에 삭제/VACUUM/클라우드 병합을 시작할 수 있다.
  3. 뉴스 제목·요약·메모 등 신뢰할 수 없는 문자열을 CSV에 그대로 기록해, 스프레드시트에서 열 때 수식으로 해석될 수 있다.
- **데이터 손상/유실 가능성:** 즉시 파일을 파괴하거나 트랜잭션 밖에서 DB를 덮어쓰는 확정 경로는 발견하지 못했다. 다만 ISSUE-001은 원격 변경 반영을 누락시키고, ISSUE-002는 유지보수 결과를 비결정적으로 만들 수 있다. 백업 복원은 사전 검증·staging·rollback을 사용하므로 보호 수준이 양호하다.
- **가장 먼저 수정할 영역:** 클라우드 오류 분류 → 유지보수 worker barrier → CSV 안전 인코딩 순이다.

## 2. Project Understanding

### 프로젝트 목적

NAVER API HUB의 뉴스 검색 API를 이용해 여러 검색 탭을 주기적으로 수집하고, 기사와 사용자 상태를 로컬에 장기 보존·검색·분류하는 앱이다. 핵심 사용자 기능은 탭별 canonical query, 제외어, 날짜/출처/태그/읽음/중복 필터, 아카이브 검색, 기사 상태 관리, CSV/Markdown/JSON 내보내기, 설정 이동, 자동 백업, 폴더 기반 다중 PC 동기화, GitHub Release 업데이트다.

### 주요 entrypoint와 핵심 모듈

- `news_scraper_pro.py` — compatibility facade 및 실행 스크립트
- `core.bootstrap.main()` — 런타임 파일 마이그레이션, 단일 인스턴스, pending restore, QApplication/MainApp 부팅, 전역 오류·signal 처리
- `ui.main_window.MainApp` — UI와 fetch/IO/유지보수/종료 orchestration
- `core.workers_support.api_worker.ApiWorker` — NAVER 요청, retry/cancel, 파싱, DB upsert, 결과 signal
- `core.database.DatabaseManager` — schema/migration, connection pool, query/mutation/cloud merge facade
- `core.backup_support` — SQLite snapshot, 백업 검증, 안전한 삭제·예약 복원·rollback
- `core.cloud_sync_support` / `core.db_cloud_sync_support` — ZIP snapshot, 선택·격리, preview/merge, conflict timestamp 처리
- `core.config_store_support` — 설정 정규화, 원자적 저장, `.backup` 복구, Windows DPAPI secret 저장
- `core.update_manifest` / `core.update_installer` — Ed25519 manifest 검증, HTTPS·크기·SHA-256 검증, 별도 helper 교체·smoke·rollback

### 데이터 저장 방식

- 기본 Windows 데이터 루트: `%LOCALAPPDATA%\NaverNewsScraperPro`
- 실제 파일명: `news_database.db`, `news_scraper_config.json`, `news_scraper.log`, `keyword_groups.json`, `pending_restore.json`, `backups/`
- SQLite는 WAL, foreign keys, busy timeout, connection pool을 사용한다.
- 기사 본체는 `news`, 검색 탭 소속은 `news_keywords`, 태그는 `news_tags`와 관련 상태 테이블에 분리된다.
- 읽음·북마크·메모·삭제·태그의 갱신 timestamp를 사용해 cloud merge 충돌을 해소한다.

### 외부 의존성

- Runtime: Python, PyQt6, requests/urllib3, cryptography, stdlib SQLite
- 서비스: NAVER API HUB, GitHub raw manifest/Release asset
- OS 기능: Windows registry startup, DPAPI, system tray, local socket/lock
- 선택적 저장소: OneDrive/Google Drive/Dropbox/NAS 등 사용자가 지정한 동기화 폴더

### 핵심 실행 흐름

```text
앱 시작
news_scraper_pro.py
→ core.bootstrap.main()
→ legacy runtime migration / single-instance lock / pending restore
→ MainApp(runtime_paths)
→ DatabaseManager integrity check + schema migration + connection pool
→ tabs hydrate from SQLite
→ QApplication event loop

뉴스 수집
탭 검색어
→ parse_search_query() / build_fetch_key() / credential guard / dedupe·cooldown guard
→ ApiWorker (QThread)
→ NAVER API HUB (timeout, no redirect, retry/backoff)
→ response normalization + exclusion filter
→ DatabaseManager.upsert_news_detailed() transaction
→ finished/error signal
→ stale request 확인 → tab reload / badge / notification / paging cursor

기사 상태
카드 action
→ link/field validation + note/tag normalization
→ DatabaseManager mutation transaction
→ local cache/card/badge refresh
→ cloud snapshot에서 timestamp 기반 병합

백업·복원
수동/타이머
→ SQLite backup API (실패 시 sidecar copy fallback)
→ payload self-verification
→ backup root containment
→ pending_restore.json 원자 저장
→ 다음 부팅 전 source 검증 + staging snapshot
→ atomic replace → 실패 시 rollback

클라우드 동기화
타이머/수동 명령
→ maintenance mode
→ local SQLite snapshot + sanitized config ZIP
→ unseen remote snapshot 선택/preview
→ DatabaseManager.merge_cloud_snapshot_db() transaction + rollback copy
→ seen snapshot 기록 / UI hydration

업데이트
UI 확인
→ HTTPS manifest download
→ Ed25519 signature / version / expiry / URL / size validation
→ streamed artifact size + SHA-256 validation
→ helper launch → MainApp.real_quit() 안전 종료
→ target backup / replace / --smoke / restart
→ 실패 시 이전 EXE rollback + next-start result 표시
```

## 3. Audit Coverage & Limitations

### 확인 범위

- 문서·설정: `README.md`, `CLAUDE.md`(Windows의 case-insensitive 경로로 실제 `claude.md` 확인), `AGENTS.md`, `pytest.ini`, `pyrightconfig.json`, `news_scraper_pro.spec`, `.specify/feature.json`, 기존 감사 이력
- 부팅·종료: `news_scraper_pro.py`, `core/bootstrap.py`, runtime migration/path, startup registry, single-instance IPC, `MainApp.closeEvent()` 및 worker 정리
- 네트워크·검색: query parser, NAVER API helper, ApiWorker, HTTP policy, fetch start/completion/error, pagination/cooldown
- DB: manager/pool, schema/migration/integrity recovery, fetch/count/archive, upsert, 상태·태그·삭제, FTS 정책, DBWorker
- 파일·설정: atomic config save/recovery, DPAPI/plain fallback, import/export
- 백업·클라우드: backup create/verify/delete/pending restore/rollback, snapshot ZIP validation/path policy/quarantine, preview/merge/rollback
- 업데이트: manifest, staged download, helper, smoke, rollback, result/cleanup

### CodeGraph 사용 내용

`.codegraph/`가 존재해 일반 코드 검색 전에 `codegraph explore`를 사용했다. 다음 call path와 blast radius를 구조적으로 확인했다.

- `news_scraper_pro.py → core.bootstrap.main → MainApp → closeEvent/_perform_real_close`
- `MainApp.fetch_news → ApiWorker.run → naver_api → upsert_news_detailed → on_fetch_done/on_fetch_error`
- `DatabaseManager → schema/integrity/pool → fetch/count/upsert/cloud merge`
- `MainApp cloud handlers → run_cloud_sync_cycle/import_cloud_snapshot → merge_cloud_snapshot_db`
- `AutoBackup → verify_backup_payload → schedule_restore → apply_pending_restore_if_any → rollback`
- `update UI → verify_release_manifest → prepare_staged_update → launch_update_helper → apply_staged_update`
- ISSUE-001~003 관련 `run_cloud_sync_cycle`, `_run_cloud_sync_once`, `cleanup_worker`, `_cancel_active_fetch_workers`, `_export_row`의 production callers와 영향 모듈

CodeGraph가 mixin의 동적 dispatch 또는 동명 symbol을 완전히 연결하지 못한 부분은 현재 파일 직접 열람과 `rg`로 보완했다.

### 실행한 검증

- `python -m pyright` → **0 errors, 0 warnings**
- `python -m compileall -q core ui news_scraper_pro.py` → **성공**
- 핵심 집중 테스트 18개 파일 → **100 passed, 5 subtests passed**
  - NAVER API/HTTP policy, ApiWorker session·cancel
  - DB integrity recovery
  - cloud sync/quarantine/refresh blocking
  - backup collision/restore/pending restore
  - config secret/roundtrip
  - update manifest/installer
  - runtime paths/query parser/maintenance/encoding
- 전체 suite 1차 실행 → **collection 단계에서 5 errors**
- QtNetwork 의존 5개 파일을 제외한 실행 → **322 passed, 1 failed, 5 subtests passed**. 유일한 실패도 `test_entrypoint_bootstrap`의 같은 QtNetwork import 실패였다.
- CSV formula 보존 재현 → 제목 `=1+1`이 export 결과 첫 cell에 그대로 기록됨을 확인했다.

### 한계

- 현재 환경은 Python 3.14.7, PyQt6 6.11.0, PyQt6-Qt6 6.11.1이며 `PyQt6.QtNetwork`가 DLL load error `0xc0000139`로 import되지 않았다. 따라서 실제 MainApp 부팅, single-instance IPC, system tray, Qt event-loop E2E는 실행하지 못했다. 이 환경 오류를 곧바로 제품 코드 결함으로 분류하지 않았다.
- NAVER API HUB 실제 계정/키와 외부 네트워크 호출은 수행하지 않았다.
- 실제 OneDrive/Dropbox/NAS의 동시 동기화, Windows 종료 신호, Registry/DPAPI 실기기 동작, PyInstaller one-file 빌드·EXE 자기 업데이트는 실행하지 않았다.
- macOS/Linux는 README상 지원 대상이 아닌 Windows 전용 앱이므로 런타임 E2E를 평가하지 않았다. 경로 helper의 정적 동작만 확인했다.

## 4. High-Risk Issues

이번 감사에서는 **Critical/High 심각도 이슈는 확인되지 않았다.** 아래는 신뢰도가 Confirmed이거나 근거가 강한 Likely인 production 이슈다.

### [ISSUE-001 — Resolved in v32.8.0] 일시적 클라우드 병합 오류도 정상 스냅샷을 영구 격리함

- **위치:** `core/cloud_sync_support/import_flow.py:187-214`, `core/cloud_sync_support/import_flow.py:226-259`, `ui/main_window_io_support/cloud.py:257-280`, `core/cloud_sync_support/snapshot_io.py:81-103`
- **우선순위:** Medium
- **신뢰도:** Confirmed
- **문제:** manifest/ZIP 검증 오류뿐 아니라 `preview_cloud_snapshot_import()` 또는 `import_cloud_snapshot()`가 던지는 모든 예외를 `except Exception`으로 잡아 `quarantine_invalid_snapshot()`을 호출한다. 이 함수는 원본 ZIP을 동기화 루트의 `.invalid` 디렉터리로 이동한다.
- **발생 조건:** 유효한 스냅샷을 preview/merge하는 동안 SQLite busy/locked, disk full, pool/connection failure, 임시 디렉터리 권한 오류, 예상하지 못한 로컬 코드 예외가 발생할 때다.
- **영향:** 정상 원격 스냅샷이 다음 자동/수동 동기화 후보에서 사라져 해당 변경을 재시도하지 않는다. 원본이 `.invalid`에 남아 물리적으로 삭제되지는 않지만, 사용자가 수동 복구하거나 원격 PC가 새 전체 snapshot을 만들기 전까지 변경 반영이 누락될 수 있다.
- **근거:** selection 단계의 manifest 오류 격리는 타당하지만, selection을 통과한 snapshot도 preview loop와 import loop의 포괄 예외에서 동일하게 이동된다. CodeGraph상 이 경로는 수동 import, full sync, `run_cloud_sync_cycle()` 모두에서 production reachable하다.
- **반증 확인:** `read_snapshot_manifest()`/`extract_snapshot()`의 크기·member·path 검증, merge transaction rollback, snapshot seen-id, 유지보수 모드를 확인했다. 이 보호 장치들은 DB 변경 원자성은 지키지만 “예외 원인이 스냅샷 손상인가”를 분류하지 않으므로 오격리를 막지 못한다. quarantine은 recoverable move이지만 자동 retry 경로는 없다.
- **호출/영향 범위:** `MainApp._run_cloud_sync_once()` → manual preview/import 또는 `run_cloud_sync_cycle()` → `import_cloud_snapshot()` → `DatabaseManager.merge_cloud_snapshot_db()`; 클라우드 상태, seen-id, 이후 snapshot selection과 multi-PC 일관성에 영향.
- **권장 수정 방향:** snapshot 구조/무결성 예외(`CloudSyncError` 중 validation 계열)만 격리한다. DB/IO/lock/space 오류는 원본을 그대로 두고 retryable error로 반환하며 bounded retry/backoff와 사용자 안내를 적용한다. preview 실패는 snapshot을 이동하지 않아야 한다.
- **필요한 회귀 테스트:** 유효 ZIP + `merge_cloud_snapshot_db()`가 `DatabaseWriteError("database is locked")`를 던질 때 ZIP이 원위치에 남고 다음 cycle에서 재선택되는지 검증한다. 반대로 잘못된 manifest, zip-slip, 과대 payload는 계속 `.invalid`로 이동해야 한다.

### [ISSUE-002 — Resolved in v32.8.0] 유지보수가 실제로 끝나지 않은 fetch worker와 중첩될 수 있음

- **위치:** `ui/main_window_support/base_support/maintenance.py:85-117`, `ui/main_window_fetch_support/worker_flow_support/completion.py:347-430`
- **우선순위:** Medium
- **신뢰도:** Likely
- **문제:** 첫 `cleanup_worker()`가 timeout이면 `_cancel_active_fetch_workers()`는 즉시 `force=True, wait_ms=0`으로 재호출한다. 실제 thread가 계속 실행 중이어도 `cleanup_worker()`는 handle을 registry에서 분리하고 `True`를 반환한다. 호출자는 이를 “종료 완료”로 해석해 maintenance mode를 시작한다.
- **발생 조건:** requests 호출, retry sleep 또는 DB upsert 중인 fetch가 1.5초 내 종료되지 않은 상태에서 오래된 기사 삭제, 전체 삭제, VACUUM, CSV import, mark-all-read, cloud sync 같은 유지보수 작업을 시작할 때다.
- **영향:** 네트워크 단계에서 stop flag를 본 worker는 보통 DB write 전에 종료하지만, 이미 upsert transaction에 진입한 worker는 내부 cancellation check 없이 계속될 수 있다. 삭제 직후 기사가 다시 삽입되거나 VACUUM/merge가 lock 대기·실패할 수 있고, 유지보수의 배타성 보장이 이름과 다르게 된다.
- **근거:** `cleanup_worker()`의 timeout branch는 `retain_qthread_until_finished()` 후 `force`이면 `_detach_worker_handle()`하고 `True`; `_cancel_active_fetch_workers()`는 그 반환값이 `True`면 unfinished 목록에 넣지 않는다. 기존 `test_begin_database_maintenance_force_detaches_worker_after_cleanup_timeout`도 현재 동작을 성공으로 고정한다.
- **반증 확인:** `ApiWorker.stop()`의 running flag, response 직후·upsert 직전 cancellation check, SQLite transaction/WAL/busy timeout, tab background task의 별도 cancellation을 확인했다. 이들은 대부분의 network-wait 경우를 안전하게 만들지만 이미 시작된 DB transaction을 중단하지 않으며, registry 분리는 thread completion barrier가 아니다.
- **호출/영향 범위:** settings data tasks(delete old/all, optimize), `NewsTab.mark_all_read`, CSV import, cloud sync가 `begin_database_maintenance()`를 사용한다. CodeGraph상 `cleanup_worker()`는 fetch replacement, tab lifecycle, shutdown, maintenance에서도 공유된다.
- **권장 수정 방향:** force-detach와 “완료”를 별도 상태로 반환한다. maintenance는 모든 DB-writing fetch가 실제 종료했거나, DB connection/transaction이 반환됐다는 barrier를 확인한 뒤에만 시작한다. timeout이면 작업을 취소하고 사용자에게 재시도를 안내하는 편이 안전하다.
- **필요한 회귀 테스트:** upsert 진입 후 event로 block되는 가짜 worker를 두고 maintenance 요청이 `False`를 반환하는지, transaction 종료 후 재요청만 성공하는지 검증한다. delete-all 직후 지연 upsert가 기사를 재삽입하지 않는 concurrency regression도 필요하다.

### [ISSUE-003 — Resolved in v32.8.0] CSV export가 스프레드시트 수식 주입을 그대로 허용함

- **위치:** `ui/main_window_io_support/exports.py:49-61`, `ui/main_window_io_support/exports.py:92-119`, `ui/main_window_io_support/exports.py:179-263`
- **우선순위:** Medium
- **신뢰도:** Confirmed
- **문제:** `_export_row()`가 API에서 받은 제목·설명·출처와 사용자 메모·태그를 그대로 `csv.writer`에 전달한다. `=`, `+`, `-`, `@` 또는 제어문자로 시작하는 cell을 spreadsheet-safe하게 중화하지 않는다.
- **발생 조건:** 뉴스 제공자 또는 import된 메모/태그가 수식 prefix로 시작하고, 사용자가 결과 CSV를 Excel/LibreOffice 등 수식을 평가하는 프로그램에서 열 때다.
- **영향:** 외부 URL 호출, 오해를 유발하는 계산 결과, 사용 환경에 따라 DDE/수식 기반 정보 노출이 가능하다. 앱 자체에서 CSV를 열지는 않으므로 즉시 코드 실행으로 과장하지 않았고 Medium으로 평가했다.
- **근거:** 임시 파일 재현에서 title `=1+1`이 CSV 첫 cell에 그대로 기록됐다. 작은 목록 export와 chunked scope export 모두 `_export_row()`를 공유한다.
- **반증 확인:** `csv.writer`의 quoting과 UTF-8-SIG, atomic temp/replace, URL 정규화를 확인했다. CSV quoting은 delimiter/newline만 보호하며 spreadsheet formula evaluation을 막지 않는다. 링크가 HTTP(S)로 제한돼도 title/description/notes/tags는 별도 신뢰 경계다.
- **호출/영향 범위:** 현재 탭 export, 아카이브 export, background chunk export와 호환 facade가 모두 영향을 받는다. JSON/Markdown export에는 동일한 spreadsheet formula 문제는 없다.
- **권장 수정 방향:** CSV 전용 cell sanitizer를 두고 위험 prefix(선행 whitespace/control 포함)를 apostrophe 등으로 중화한다. 원문 보존이 필요하면 “spreadsheet-safe CSV”를 기본으로 하고 raw export를 명시적 고급 옵션으로 분리한다.
- **필요한 회귀 테스트:** `=1+1`, `+SUM(1,2)`, `-1+2`, `@SUM(A1:A2)`, `\t=...`, `\r=...`가 안전하게 출력되고 일반 한글·URL·메모 roundtrip은 유지되는지 검증한다.

## 5. Potential Functional Gaps

### [GAP-001 — Resolved in v32.8.0] CSV import의 파일 단위 원자성과 부분 적용 결과가 없음 — Likely Gap

`import_bookmarks_notes_from_csv()`는 각 행에서 bookmark와 note를 서로 다른 DB transaction으로 갱신하고, 파일 전체도 하나의 transaction이 아니다. 중간 예외나 취소 시 앞선 변경은 이미 commit되지만 UI는 단순 “실패/취소”만 표시하고 적용된 행 수를 제공하지 않는다. 대용량 streaming import에서 부분 commit 자체는 합리적일 수 있으나, resume/idempotency 또는 “N행까지 적용됨” 계약이 필요하다.

### [GAP-002 — Resolved in v32.8.0] dependency 재현성 파일과 지원 Python 상한이 없음 — Confirmed Gap

저장소에는 `requirements.txt`, lockfile 또는 `pyproject.toml` dependency 선언이 없고 README는 `pip install PyQt6 requests cryptography`와 Python 3.10 이상만 안내한다. 감사 환경의 최신 Python/PyQt 조합에서는 QtNetwork DLL import가 실패해 전체 suite와 앱 entrypoint 검증이 막혔다. 이것이 소스 결함이라는 증거는 아니지만, 알려진 정상 조합을 재현할 수 없는 것은 runtime 안정성·CI 신뢰도의 명확한 공백이다.

### [GAP-003] 실제 외부 서비스·패키지 E2E가 없음 — Likely Gap

mock 기반 API/클라우드/update 테스트는 풍부하지만 다음 production story를 한 번에 검증하는 자동화가 확인되지 않았다.

- 패키지 EXE 부팅 → QtNetwork single-instance IPC → MainApp 표시/종료
- 실제 NAVER API HUB sandbox/검증 계정의 200, 401/403, 429 계약
- 두 독립 DB가 공유 폴더 snapshot을 교환하는 multi-process/cloud-drive 시뮬레이션
- one-file 이전 EXE → signed local release → 교체 → smoke → 재시작/rollback

### [GAP-004 — Resolved in v32.8.0] cloud quarantine 복구 UX가 없음 — Confirmed Gap

`.invalid`로 이동한 ZIP과 `.reason.txt`는 남지만 UI에서 목록·재검증·원위치 복구 기능은 확인되지 않았다. ISSUE-001을 수정하더라도 실제 손상 snapshot을 사용자가 진단·삭제·복구하는 운영 경로가 있으면 지원성이 높아진다.

## 6. Documentation Mismatches

1. **README runtime 파일명이 구현과 다름.** `README.md:295-296`은 `news_data.db`, `config.json`을 안내하지만 `core/runtime_support/paths.py`의 실제 기본값은 `news_database.db`, `news_scraper_config.json`이다. 사용자가 수동 백업·로그 지원 시 잘못된 파일을 찾게 된다.
2. **Spec Kit 활성 feature 설명이 서로 다름.** `.specify/feature.json`과 실제 `claude.md`는 `specs/002-github-release-updates`를 가리키지만 `AGENTS.md`는 `specs/001-news-tabsearch-user-readme`를 활성 feature로 기록한다. 또한 AGENTS의 001 feature는 `tasks.md`를 먼저 읽으라고 하지만 해당 파일은 존재하지 않는다.
3. **문서 파일 case가 지침과 다름.** 저장소에는 `claude.md`만 tracked되어 있으나 사용자/도구 지침은 `CLAUDE.md`를 가리킨다. Windows에서는 열리지만 case-sensitive 환경과 Git checkout에서는 다른 경로다.
4. **소스 실행 지원 범위가 과도하게 열려 있음.** README의 “Python 3.10 이상”은 상한·검증 버전·dependency version 없이 제시된다. 이번 Python 3.14 환경의 QtNetwork import 실패를 고려하면 “검증된 버전”과 lock/install 절차를 명시해야 한다.

NAVER API HUB URL/header, legacy Developers Center 비지원, config key 이름, PyInstaller `runtime_tmpdir=None`, 현재 version/update history 계약은 구현과 일치했다.

## 7. Recommended Fix Plan

### Phase 1 — Immediate

1. cloud preview/import 예외를 snapshot validation 오류와 retryable local DB/IO 오류로 분류하고, 후자는 격리하지 않는다.
2. maintenance 진입에서 force-detached thread를 완료로 간주하지 말고 DB-writing worker completion barrier를 강제한다.
3. 모든 CSV export 경로에 공용 spreadsheet-safe cell sanitizer를 적용한다.

### Phase 2 — Stability

1. CSV import의 partial-commit 정책을 문서화하고 applied/skipped/unchanged/failed-row 결과와 resume 가능한 line 정보를 반환한다.
2. cloud retry/backoff, quarantine 관리 UI, 원본 복구·재검증 흐름을 추가한다.
3. 검증된 Python/PyQt/requests/cryptography 버전을 dependency 파일로 고정하고 깨끗한 Windows 환경에서 전체 suite와 entrypoint smoke를 실행한다.
4. README의 runtime 파일명과 Spec Kit 포인터/case를 현재 코드에 맞춘다.

### Phase 3 — Structural

1. worker cleanup 반환값을 `finished / cancelled / detached_running / failed` 같은 명시적 상태로 바꿔 shutdown, tab mutation, maintenance가 서로 다른 정책을 적용하게 한다.
2. cloud 예외 taxonomy를 validation, transient storage, DB conflict, local resource failure로 분리한다.
3. PyInstaller one-file E2E와 로컬 signed update fixture를 CI에 추가한다.

실제 코드는 이번 감사에서 수정하지 않았다.

## 8. Test Recommendations

### Unit

- `test_cloud_transient_merge_error_does_not_quarantine`: 유효 ZIP + `DatabaseWriteError("locked")`; 원본 유지, retryable status, seen-id 미기록을 기대한다.
- `test_cloud_validation_error_is_quarantined`: missing manifest, zip-slip, 과대 entry는 `.invalid`와 reason file 생성을 기대한다.
- `test_csv_export_neutralizes_formula_prefixes`: 위험 prefix와 선행 제어문자를 parameterize하고 안전 prefix 적용을 기대한다.
- `test_csv_import_reports_unchanged_separately`: 존재하지만 값이 같은 기사와 link가 없는 기사를 `unchanged`/`missing`으로 구분한다.

### Integration

- `test_maintenance_waits_for_inflight_upsert`: 실제 SQLite manager와 upsert 중간 barrier를 사용해 maintenance가 먼저 시작되지 않는지 검증한다.
- `test_delete_all_cannot_race_with_detached_fetch`: 지연 upsert와 delete-all을 교차시켜 완료 후 DB가 의도한 최종 상태인지 검증한다.
- `test_cloud_retry_after_locked_database`: 첫 merge는 lock으로 실패, 두 번째는 성공; ZIP 원위치·최종 seen-id·상태 merge를 검증한다.
- `test_csv_import_partial_failure_contract`: N번째 행에서 write error를 주입하고 commit된 행 수·실패 line·재실행 idempotency를 검증한다.

### End-to-End

- clean Windows VM에서 설정 저장 → 탭 생성 → mock/local HTTP NAVER-compatible response → DB 저장 → 앱 재시작 → 기사 재조회 → 읽음/메모/북마크 → CSV export까지 검증한다.
- 두 앱 데이터 디렉터리와 한 공유 폴더로 A export → B import/edit/export → A import를 수행해 timestamp conflict와 삭제/복구를 확인한다.
- 이전 one-file EXE에서 서명된 로컬 artifact를 받아 update → graceful shutdown → smoke → restart → result consume까지 수행하고, smoke failure에서는 원본 EXE 복원과 다음 실행 알림을 확인한다.

### Concurrency

- fetch, FTS backfill, export, tray unread query가 동시에 실행되는 동안 cloud sync/delete/VACUUM 진입을 반복해 미종료 worker가 maintenance와 겹치지 않는지 검증한다.
- connection pool 고갈과 emergency cap에서 모든 connection이 반환되고 UI가 명시적 과부하 오류를 표시하는지 장시간 반복한다.

### Regression

- query key가 같은 대소문자/제외어 순서 조합, tab rename/close 직후 stale result, load-more start 1000 경계, count/badge/export scope parity를 유지한다.
- note 10,000자 제한을 dialog, CSV import, cloud merge, settings/export contract에서 동일하게 검증한다.
- backup restore 중 config 교체 후 DB 교체 실패, WAL sidecar 실패, rollback 실패 주입 시 원본 보존과 pending file 상태를 검증한다.

### Platform-specific

- Windows 10/11의 검증된 Python/PyQt 조합과 PyInstaller EXE에서 QtNetwork, tray, registry startup, DPAPI, Unicode 사용자 경로를 검증한다.
- OneDrive 동기화 중 rename/lock, 네트워크 드라이브 지연, FAT/NTFS 권한 차이에서 snapshot atomic replace와 retry를 검증한다.
- case-sensitive CI에서 `claude.md`/`CLAUDE.md` 참조와 모든 문서 경로가 유효한지 확인한다.

## 9. Final Assessment

| 영역 | 평가 | 근거 |
|---|---|---|
| Functional Correctness | **Good** | 감사에서 확인한 cloud, maintenance, CSV 결함을 수정하고 직접 회귀 테스트로 고정했다. |
| Runtime Stability | **Acceptable** | worker barrier와 dependency/CI 계약을 보완했다. 다만 현재 전역 Python 환경의 QtNetwork DLL 충돌로 full collection은 완료하지 못했다. |
| Data Integrity | **Good** | SQLite transaction/WAL, atomic config, backup verify/staging/rollback, cloud merge rollback이 강하다. 직접 데이터 파괴 결함은 확인되지 않았다. |
| Error Resilience | **Good** | cloud validation/transient 분류, 원본 보존, quarantine recovery와 CSV 부분 결과가 추가됐다. |
| Cross-platform Robustness | **Acceptable** | Windows 전용 계약, 실제 runtime 파일명, 검증 dependency와 case-sensitive guide 경로를 정리했다. macOS/Linux는 지원 범위 밖이다. |
| Test Confidence | **Acceptable** | 변경 집중 48 passed/5 subtests, 비-Qt 포함 광범위 회귀 333 passed/10 subtests, pyright 0, PyInstaller 성공이다. 전역 환경의 QtNetwork 충돌과 외부 E2E는 남았다. |

실제로 먼저 수정할 문제 3개는 모두 v32.8.0에서 반영됐다:

1. **ISSUE-001:** 정상 cloud snapshot의 transient-error quarantine 중단 및 retry 분류 — 완료
2. **ISSUE-002:** maintenance 진입 전 실제 fetch/DB transaction completion barrier 보장 — 완료
3. **ISSUE-003:** 모든 CSV export cell의 spreadsheet formula 중화 — 완료
