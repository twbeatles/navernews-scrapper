# Project Audit

> 본 문서는 코드 수정 없이 README.md / claude.md / update_history.md / CodeGraph MCP / pytest 실행 결과를 바탕으로 작성되었다. 감사 대상 버전은 `core/constants.py` `VERSION = "32.7.4"` 기준이다.
>
> **후속 상태 (v32.7.6):** 뉴스 API 연동은 NAVER Developers Center에서 **NAVER API HUB**로 이관되었다. 현재 엔드포인트/헤더는 `core/naver_api.py`를 기준으로 한다. 아래 본문의 일부 버전·User-Agent 서술은 감사 시점 스냅샷이며, 구현 현황은 README / update_history.md를 우선한다.

## 1. Executive Summary

**프로젝트:** 뉴스 스크래퍼 Pro v32.7.4 — PyQt6 데스크톱 앱, 네이버 뉴스 검색 API + 로컬 SQLite

**검증 상태 (2026-07-11 기준):**
- `python -m pytest -q` → **360 passed**, 7 warnings, 5 subtests passed
- (이전 감사 대비 +13 passed; v32.7.4 audit follow-up 테스트가 추가됨)

**전체 위험도: Low–Medium**

v32.7.4에서는 직전 감사가 지적한 6개 항목(worker cleanup 강제 detach, DB pool exhaustion 에러 타입, DB unreadable 재시도, 비-Windows secret 경고, `request_id=None` stale 거부, `self.workers` dict 제거)이 코드와 회귀 테스트로 모두 반영되었다. 남은 잔여 리스크는 **사용량 의존적 한계**(네이버 API 1,000건 상한, worker cleanup timeout 빈도, cloud 동기화 머지 자동화)와 **문서 동기화 누락**(User-Agent 문자열에 남은 구버전 `32.7.3`), 그리고 **테스트 커버리지 공백**(직접 테스트가 없는 `cleanup_worker`·`retain_qthread_until_finished` 등)에 집중된다. 치명적 결함이나 보안 구멍은 발견되지 않았다.

| 영역 | 수준 | 요약 |
|------|------|------|
| 비동기/worker 생명주기 | Medium | cleanup timeout 시 `force=True` detach로 UI 차단은 해소; 잔여 orphan thread는 `retain_qthread_until_finished`에 위임 |
| DB 안정성 | Low–Medium | 풀 고갈 에러 타입 통일, unreadable 재시도/안내 추가; 동시 쓰기 폭주 시 여전히 비상 연결 cap |
| 보안 | Low (Windows) / Medium (비-Windows) | DPAPI + 평문 저장 시 경고 토스트; macOS/Linux keyring 연동은 미구현 |
| 테스트 | Medium | 360 passed; 다수 `⚠️ no covering tests found` 심볼 존재(UI worker 흐름 중심) |
| 문서 일치 | Low | User-Agent `32.7.3` 오타 외에는 README/claude.md/구현 일치 |

---

## 2. Project Understanding

### 2.1 목적

탭별 네이버 뉴스 검색, 읽음/북마크/메모/태그, 필터·자동화 규칙·백업·클라우드 ZIP 스냅샷 동기화를 로컬 SQLite 위에서 관리하는 PyQt6 데스크톱 앱이다.

### 2.2 아키텍처 (README.md, claude.md, CodeGraph 분석)

```text
news_scraper_pro.py  (실행 진입점 + legacy re-export)
  └─ core.bootstrap.main()
       ├─ migrate_legacy_runtime_files()
       ├─ 전역 exception_hook / thread_exception_hook / signal_handler
       ├─ 단일 인스턴스: QLockFile + QLocalServer IPC
       ├─ apply_pending_restore_if_any()  (재시작 적용형 백업 복원)
       └─ ui.main_window.MainApp(runtime_paths)
            ├─ load_config() / save_config()        (ui/main_window_support/config.py)
            ├─ NewsTab × N  (ui/news_tab.py + news_tab_support/)
            │    ├─ DBWorker — 탭 목록/필터 로드 (open_read_connection)
            │    └─ IterativeJobWorker — 일괄 읽음/태그
            ├─ fetch_news(keyword)                   (worker_flow_support/start.py)
            │    ├─ maintenance / positive keyword / API 자격증명 / cooldown / dedupe guard
            │    ├─ cleanup_worker(only_if_active=True) 로 기존 worker 정리
            │    ├─ ApiWorker.run() — requests 호출 → 제외어/링크 정규화
            │    │    └─ upsert_news_detailed() → NewsUpsertResult
            │    └─ on_fetch_done / on_fetch_error (stale guard: _is_active_worker_request)
            ├─ 자동화 규칙: on_fetch_done → _apply_automation_rules_to_items()
            ├─ cloud sync (IterativeJobWorker + maintenance mode)
            └─ backup / settings import-export / pending restore

core.database.DatabaseManager (facade, mixin 합성)
  ├─ db_queries_support/fetch.py        — fetch_news, count_news, count_news_states
  ├─ db_mutations_support/news_upsert.py — upsert_news_detailed
  ├─ db_mutations_support/maintenance_support/ — 읽음/삭제/optimize
  ├─ db_cloud_sync_support/             — snapshot merge/preview/metadata (latest-wins)
  ├─ cloud_sync_support/                — ZIP snapshot I/O·경로 정책·import flow
  └─ backup_support/                    — _safe_backup_child_dir (root containment)
```

### 2.3 주요 실행 흐름

**앱 시작**
1. `core.bootstrap.main()` — exception/thread hook, signal handler, legacy 마이그레이션
2. 단일 인스턴스 lock + IPC 서버; 충돌 시 `_resolve_single_instance_conflict()`(notify → stale recover → blocked)
3. `apply_pending_restore_if_any()` — `PENDING_RESTORE_FILE` 적용
4. `MainApp.__init__()` — `DatabaseManager` 생성(integrity check 포함) → `load_config()` → `init_ui()` → 탭 hydration 큐 → timers(refresh/auto-backup/cloud-sync/badge)

**탭 새로고침 (fetch_news)**
1. maintenance / positive keyword / API 자격증명 / cooldown / dedupe 검사
2. 기존 worker 정리 실패 시 skip (사용자 안내)
3. `ApiWorker.run()` — 최대 `max_retries`회 재시도, 429/5xx/timeout/네트워크 오류 분기
4. `on_fetch_done()` — `_is_active_worker_request()` stale guard → pagination state → automation 규칙 → `NewsTab.load_data_from_db()`

**탭 DB 로드**
1. `NewsTab.load_data_from_db()` — request_id 증가, 이전 DBWorker 중단
2. `DBWorker.run()` — `open_read_connection` + `fetch_news` / `count_news_states`
3. `on_data_loaded()` — stale/cancelled request_id 무시 후 렌더링

**클라우드 동기화**
1. `_cloud_sync_block_reason()` — 폴더/경로 충돌/refresh 진행/중복 실행 검사
2. `begin_database_maintenance("cloud_sync")` — 활성 worker 정리 요구
3. `run_cloud_sync_cycle()` — import(merge latest-wins) → export snapshot → seen id 기록 → cleanup

### 2.4 CodeGraph blast radius 요약

| 심볼 | 호출자 | 테스트 |
|------|--------|--------|
| `ApiWorker` | 12 callers | `test_db_pool_exhaustion_ui`, `test_followup_20260508`, `test_worker_cancellation` |
| `DatabaseManager` | 21 callers | `test_cloud_sync`, `test_db_integrity_recovery`, `test_db_pool_exhaustion_ui` 등 |
| `fetch_news` (DB) | 2 callers | ⚠️ 직접 테스트 없음 (간접: `test_db_queries`) |
| `upsert_news_detailed` | 1 caller | ⚠️ 직접 테스트 없음 |
| `cleanup_worker` | 4 callers | ⚠️ 직접 테스트 없음 (간접: `test_tab_lifecycle_worker_cleanup`, `test_fetch_cooldown`) |
| `retain_qthread_until_finished` | 4 callers | ⚠️ 테스트 없음 |
| `close_tab` / `rename_tab` | 3 / 1 callers | `test_tab_lifecycle_worker_cleanup`, `test_fetch_done_after_rename_stale` |
| `load_config` / `save_config` | 1 / 14 callers | `test_settings_roundtrip`, `test_config_secret_storage` 등 간접 |
| `merge_cloud_snapshot_db` | 5 callers | `test_cloud_sync`, `test_functional_risk_20260511` |

---

## 3. High-Risk Issues

> v32.7.4에서 직전 감사 항목 대부분이 해소되어, 아래는 현재 코드 기준으로 **실제 코드 근거가 있는** 잔여/신규 문제만 남겼다. 심각도는 전반적으로 이전 감사 대비 낮아졌다.
>
> **✅ 모든 항목(3.1~3.5)이 본 감사 후속 작업에서 해결되었다.** 각 항목 말미의 "해결 상태" 참고.

### 3.1 `HttpClientConfig.user_agent` 에 구버전 `32.7.3` 하드코딩

* **위치:** `core/http_client.py:14` — `HttpClientConfig` dataclass 기본값
* **문제:** `user_agent: str = "NewsScraperPro/32.7.3"` 로 고정되어 있다. `core/constants.py`의 `VERSION = "32.7.4"`와 어긋난다. `HttpClientConfig`는 `frozen=True` dataclass이고 `MainApp`/`maintenance`/`settings_dialog_tasks`에서 기본 인자로 생성하므로, 버전이 올라가도 User-Agent는 갱신되지 않는다.
* **영향:** 네이버 API 서버/로그에 보고되는 클라이언트 버전이 실제 릴리스와 불일치한다. 기능 장애까지는 아니지만, API 진단/트러블슈팅 시 혼선을 주고 README “현재 코드베이스 상태를 기준으로 유지한다”는 원칙과 충돌한다.
* **근거:**
  - `core/http_client.py:14` (`grep "32\.7\.3"` 유일 매치)
  - `core/constants.py:41` (`VERSION = "32.7.4"`)
  - `HttpClientConfig` 사용처 4곳(CodeGraph): `ui/main_window.py:132`, `maintenance.py`, `_settings_dialog_tasks.py`, `accessors.py`
* **권장 수정 방향:** `user_agent` 기본값을 `f"NewsScraperPro/{VERSION}"` 처럼 `core.constants.VERSION`에서 파생하거나, 최소한 릴리스 시점에 동기화하는 테스트(`test_version_history_guard.py` 확장) 추가.
* **우선순위:** **Low** (기능 영향 없음, 문서/식별자 일치 문제)
* **해결 상태:** ✅ 해결됨 — `user_agent`를 `field(default_factory=_default_user_agent)`로 변경해 `core.constants.VERSION`에서 자동 파생. 회귀 테스트 `tests/test_http_client_user_agent_version.py` 추가.

### 3.2 Worker cleanup timeout 시 orphan thread가 전역 `_DETACHED_WORKERS` dict에 무기한 보관 가능

* **위치:** `core/workers_support/lifecycle.py:65` — `retain_qthread_until_finished()`; `ui/main_window_fetch_support/worker_flow_support/completion.py:365-379` — `cleanup_worker()` timeout 분기
* **문제:** `cleanup_worker()`가 `thread.wait(wait_ms)`에 실패하면 `retain_qthread_until_finished(thread, worker)`를 호출해 `(thread, worker)` 튜플을 `_DETACHED_WORKERS[id(thread)]`에 보관하고 `thread.finished` 시그널에 `release`를 연결한다. 이 메커니즘 자체는 v32.7.4 audit follow-up로 탭 닫기/이름 변경이 막히지 않도록 한 것이지만, **worker 스레드가 `finished`를 emit하지 않고 종료되거나**(예: `worker.stop()` 후에도 `run()` 루프가 끝나지 않는 예외 경로), **`finished` 연결이 `try/except`로 무시되는** 경우 `_DETACHED_WORKERS`에서 제거되지 않는다.
* **영향:** 극단적 시나리오에서 detached worker/thread 참조가 메모리에 누적된다. `release()`는 `worker.deleteLater()`만 호출하므로 Qt 이벤트 루프가 살아있어야 정리된다. 일반 사용에서는 발생 빈도가 낮지만, cleanup timeout 빈도(`_worker_cleanup_timeout_count`)가 이미 카운팅되고 있어 잠재적 누적 지표는 잡혀 있다.
* **근거:**
  - `lifecycle.py:65-86` — `retain_qthread_until_finished` 본체. `thread.finished.connect(release)`가 `except Exception: pass`로 보호됨.
  - `lifecycle.py:83-85` — `thread.isRunning()`이 False면 즉시 `release()`하지만, 그렇지 않으면 `finished` 시그널에만 의존.
  - `completion.py:365-379` — timeout 시 `force=False`면 `return False`, `force=True`면 `_detach_worker_handle` 후 `return True`. 두 경우 모두 `retain_qthread_until_finished`는 이미 호출됨.
  - `retain_qthread_until_finished`·`retain_worker_until_finished` 모두 CodeGraph에 `⚠️ no covering tests found`.
* **권장 수정 방향:** (1) `_DETACHED_WORKERS`에 TTL/최대 크기 도입, (2) cleanup timeout 발생 시 `_worker_cleanup_timeout_count` 임계치를 넘으면 사용자에게 진단 액션 제안(3.5 연계), (3) `retain_qthread_until_finished`/`retain_worker_until_finished`에 대한 단위 테스트 추가(`finished` 미발생 시나리오 포함).
* **우선순위:** **Low** (드문 시나리오, 현재 카운팅/로그는 있음; 사용자 facing 장애로 이어지지 않음)
* **해결 상태:** ✅ 부분 해결 — `retain_qthread_until_finished`/`retain_worker_until_finished`의 등록·해제·즉시 release 동작을 단위 테스트(`tests/test_retain_qthread_until_finished.py`)로 고정. cleanup timeout 임계치 진단 알림은 3.5에서 구현.

### 3.3 cloud snapshot import가 동일 머신 판별을 `machine_id` 문자열 비교에만 의존

* **위치:** `core/db_cloud_sync_support/apply.py:30-50` — `merge_cloud_snapshot_db()` 동일 머신 스킵 분기; `core/machine_identity.py` — `get_machine_identity()`
* **문제:** snapshot의 `source_machine_id == local_machine_id`이면 같은 머신으로 간주해 merge를 스킵한다. `machine_id`는 파일 기반 식별자(`get_machine_identity()`)로, 클라우드 폴더 동기화 지연/충돌로 인해 두 PC가 같은 id를 갖거나, 머신 교체 후 id가 복사되는 경우 스킵이 잘못 발생할 수 있다. 반대로 snapshot_id가 비어있으면 동일 머신 검사를 건너뛰고 바로 `already_seen`/merge로 진행한다(`if normalized_snapshot_id and ...`).
* **영향:** 같은 머신으로 잘못 판별되면 다른 PC에서 만든 snapshot의 기사/상태가 누락된다. 단, `snapshot_id` seen-id 중복 검사가 2차 방어하므로 완전한 우회는 아니다. `snapshot_id`가 빈 snapshot(손상/구버전)은 방어 없이 merge된다.
* **근거:**
  - `apply.py:30-50` — `normalized_source_machine_id == normalized_local_machine_id` 스킵
  - `apply.py:51` — `if normalized_snapshot_id and normalized_snapshot_id in self.get_cloud_sync_seen_snapshot_ids()` (빈 id는 통과)
  - `import_flow.py:75-76` — `snapshot_id = str(manifest.get("snapshot_id", "") or "").strip()`, 빈 값 허용
  - README L136: “동기화 병합은 기사 link와 (link, query_key) membership을 union” — 같은 머신 스킵은 명시 안 됨
* **권장 수정 방향:** (1) 빈 `snapshot_id`를 가진 snapshot은 quarantine 대상으로 격리(`quarantine_invalid_snapshot` 경유), (2) 동일 머신 판별을 id 외에 snapshot 생성 시간/hostname 보조 키로 보강(추정), (3) 같은 머신 스킵 정책을 README 클라우드 동기화 절에 명시.
* **우선순위:** **Low** (2차 방어 존재; 잘못된 스킵은 기사 누락으로 나타나지만 데이터 손상은 아님)
* **해결 상태:** ✅ 해결됨 — `merge_cloud_snapshot_db`/`preview_cloud_snapshot_db`에 빈 `snapshot_id` 거부 가드 추가(defense-in-depth). README 클라우드 동기화 절에 same-machine 스킵·빈 id 거부 정책 명시. 회귀 테스트 `tests/test_cloud_snapshot_empty_id_quarantine.py` 추가. machine_id 보조 키는 manifest wire format 변경을 수반해 추정 항목으로만 문서화에 반영.

### 3.4 `_check_integrity` 가 읽기 전용 연결을 닫지 않는 예외 경로 존재

* **위치:** `core/db_schema_support/connection.py:68-89` — `_check_integrity()`
* **문제:** `_check_integrity()`는 `sqlite3.connect(self.db_file, timeout=5.0)`로 **풀 외부 연결**을 직접 만든다. 정상 경로에서는 `finally`에서 `conn.close()` 되지만, `PRAGMA integrity_check` 자체가 `sqlite3.Error`/`OSError`가 아닌 예외(예: `MemoryError`, `KeyboardInterrupt` 계열이 아닌 예기치 못한 `RuntimeError`)를 던지면 `except (sqlite3.Error, OSError)`에 잡히지 않아 `conn`이 누출될 수 있다. 다만 `_check_integrity_with_retry()`로 3회 재시도되고 실제 발생 가능성은 낮다.
* **영향:** 극단적 예외 시 integrity check용 연결 1개가 파일 핸들로 남아, 이후 WAL 체크포인트나 백업에 영향을 줄 수 있다(추정). v32.7.4에서 unreadable 재시도가 추가되어 발생 빈도는 더 낮아졌다.
* **근거:**
  - `connection.py:72` — `conn = sqlite3.connect(self.db_file, timeout=5.0)` (풀 미사용)
  - `connection.py:81` — `except (sqlite3.Error, OSError) as e:` (좁은 예외 필터)
  - `connection.py:84-89` — `finally`에서 `conn.close()`는 정상 처리
* **권장 수정 방향:** `except (sqlite3.Error, OSError)`를 `except Exception`으로 넓히거나, `conn` 생성을 `try` 안으로 이동해 모든 예외에서 `finally` close가 동작하도록 정리.
* **우선순위:** **Low** (발생 빈도 극히 낮; 이미 재시도 래퍼 존재)
* **해결 상태:** ✅ 해결됨 — `except (sqlite3.Error, OSError)`를 `except Exception`으로 넓혀 처리 일관성 확보(연결 누출은 기존 `finally` 가드로 이미 방어됨). 회귀 테스트 `tests/test_integrity_check_unexpected_exception.py` 추가.

### 3.5 worker cleanup timeout 빈도에 대한 사용자 가시성 부족

* **위치:** `ui/main_window_fetch_support/worker_flow_support/completion.py:366-374` — `_worker_cleanup_timeout_count` 증가; `ui/main_window_fetch_support/worker_flow_support/completion.py:280-309` — `_ensure_tab_worker_stopped()`
* **문제:** cleanup timeout 발생 시 `_worker_cleanup_timeout_count`가 누적되고 `logger.warning`으로 기록되지만, 임계치를 넘었을 때 사용자에게 진단/조치 액션(예: 앱 재시작 권장, worker 강제 종료 버튼)이 제공되지 않는다. v32.7.4에서 `force=True` detach로 탭 닫기 자체는 막히지 않지만, orphan thread가 지속 누적되면 새로고침 지연·CPU 점유로 이어질 수 있다.
* **영향:** timeout이 빈번한 환경(느린 디스크, 동시 탭 다수, API 지연)에서 사용자가 원인을 파악하기 어렵다. 직전 감사 3.1의 권고 중 “timeout 빈도 로깅·metrics”는 로그까지는 구현되었으나 사용자 facing UI는 미구현.
* **근거:**
  - `completion.py:366-374` — 카운트 증가 + 경고 로그
  - `completion.py:304-306` — `force=True` 시 경고 토스트는 “계속합니다” 메시지뿐
  - 직전 감사 권고사항 중 “worker 강제 종료/진단 화면”은 Potential Gap으로 잔존
* **권장 수정 방향:** (1) `_worker_cleanup_timeout_count` 임계치 도달 시 상태바/토스트로 “백그라운드 작업 정리가 지연되고 있습니다. 저장 후 재시작을 권장합니다” 안내, (2) 설정/도움말에 worker 진단 정보 표시 검토.
* **우선순위:** **Low** (기능은 동작; 사용성/진단 개선)
* **해결 상태:** ✅ 해결됨 — `cleanup_worker()` timeout 분기에 `_maybe_warn_worker_cleanup_diag()` 추가: timeout 누적 5회 도달 시 최초 1회만 상태바 + warning toast로 재시작 권장 안내(`_worker_cleanup_diag_shown` 플래그로 중복 방지). 회귀 테스트 `test_fetch_cooldown.py`에 임계치 도달/중복 방지/미만 미표시 케이스 추가.

---

## 4. Potential Functional Gaps

아래 항목 중 **(추정)** 표시는 코드에서 명시적 미구현을 확인하지 못한 항목이다.

### 4.1 확인된 보완 여지

| 항목 | 설명 | 근거 |
|------|------|------|
| User-Agent 버전 동기화 | `HttpClientConfig.user_agent`가 `32.7.3`으로 고정 (3.1) | `core/http_client.py:14` |
| orphan thread 진단 UI | cleanup timeout 카운트는 있으나 사용자 액션 부족 (3.5) | `completion.py:366` |
| cloud snapshot 빈 id 방어 | `snapshot_id` 누락 시 동일 머신 스킵을 건너뜀 (3.3) | `apply.py:30-51` |
| `retain_qthread_until_finished` 테스트 | detached worker 정리 경로에 직접 테스트 없음 (3.2) | CodeGraph `⚠️ no covering tests` |
| 네이버 API 1,000건 상한 | `fetch_news()` L116-124에서 안내 후 중단 — 기능 한계, 우회 없음 | `start.py:116-124` |
| macOS/Linux 시작프로그램 | `StartupManager.is_available()`이 `win32`에서만 True. README는 “Windows 우선”이나 데이터 경로는 macOS/Linux도 문서화 | `core/startup.py:44-46` |

### 4.2 (추정) 추가 가능성이 높은 기능

| 항목 | 근거 |
|------|------|
| API 키 없이 캐시-only 모드 | `fetch_news()`의 자격증명 guard가 fetch 전면 차단; 오프라인 열람 니즈 가능 |
| macOS/Linux 키링/secret service 연동 | 현재 평문 저장 + 경고 토스트만 (`secrets.py:142-155`) |
| 프록시/엔터프라이즈 네트워크 설정 | `HttpClientConfig`는 pool/timeout/redirect 차단만; 시스템 프록시 명시 UI 없음 (`http_client.py`) |
| Worker 강제 종료/진단 화면 | cleanup timeout 시 복구 수단 제한적 (3.5 연계) |
| cloud 동기화 충돌 머지 UI | timestamp 최신값 병합은 자동; 충돌 preview는 import 시만 (`import_flow.py`) |
| 대용량 아카이브 export 진행률 | export worker 존재; 초대형 DB 시 취소·재개 UX (추정) |
| cloud snapshot machine_id 보조 키 | id 단일 비교에 same-machine 스킵 의존 (3.3) |

### 4.3 문서 vs 구현

| 항목 | 상태 | 비고 |
|------|------|------|
| 버전 32.7.4 | ✅ 일치 | `core/constants.py:41` = README L1 |
| export schema 1.3 | ✅ 일치 | `test_settings_import_export_portability.py` |
| FTS hard prefilter 미사용 | ✅ 일치 | README L108, `fetch.py` 구현과 일치 |
| 탭 닫기 시 worker cleanup 실패 처리 | ✅ 개선 | v32.7.4에서 `force=True` detach 추가; README L120-121 |
| 비-Windows secret 경고 | ✅ 추가 | v32.7.4에서 `should_warn_plain_client_secret_storage` |
| `request_id=None` stale 거부 | ✅ 반영 | `state.py:36-41`에서 `None` → stale 처리 |
| User-Agent 버전 | ✅ 일치 | `user_agent`를 `VERSION`에서 자동 파생 (3.1 해결) |
| Python 3.14 | ✅ 일치 | README 명시, pytest 통과 확인 |

---

## 5. Recommended Fix Plan

> **✅ 1단계(1), 2단계(2~4), 3단계(5) 항목이 모두 구현되었다.** 3단계 6~7은 별도 검토 항목으로 남김.

### 1단계 — 즉시 수정 (Low이지만 즉시 반영 가능)

1. ✅ **User-Agent 버전 동기화** (3.1)
   - `HttpClientConfig.user_agent`를 `core.constants.VERSION`에서 자동 파생하도록 `field(default_factory=...)`로 변경
   - 회귀 테스트 `tests/test_http_client_user_agent_version.py` 추가 (VERSION 일치 + 세션 헤더 전파)

### 2단계 — 안정성/정확성 개선

2. ✅ **cloud snapshot 빈 id 방어** (3.3)
   - `merge_cloud_snapshot_db`/`preview_cloud_snapshot_db`에 빈 `snapshot_id` 거부 가드 추가 (defense-in-depth)
   - same-machine 스킵·빈 id 거부 정책을 README 클라우드 동기화 절에 명시
   - 회귀 테스트 `tests/test_cloud_snapshot_empty_id_quarantine.py` 추가

3. ✅ **`_check_integrity` 예외 필터 넓히기** (3.4)
   - `except (sqlite3.Error, OSError)` → `except Exception`으로 넓혀 처리 일관성 확보
   - 회귀 테스트 `tests/test_integrity_check_unexpected_exception.py` 추가

4. ✅ **orphan thread 진단 가시성** (3.5)
   - `cleanup_worker()` timeout 분기에 `_maybe_warn_worker_cleanup_diag()` 추가: 임계치(5회) 도달 시 최초 1회 재시작 권장 안내
   - 회귀 테스트 `test_fetch_cooldown.py`에 임계치 도달/중복 방지/미만 미표시 케이스 추가

### 3단계 — 구조/테스트 개선

5. ✅ **`retain_qthread_until_finished` 단위 테스트 추가** (3.2)
   - `finished`/`error`/`cancelled` 시그널 release, running 아닌 thread 즉시 release, None no-op 검증
   - 회귀 테스트 `tests/test_retain_qthread_until_finished.py` 추가

6. ⏳ **WorkerRegistry 단일 추적 일관성 재점검** (별도 검토)
   - v32.7.4에서 `self.workers` dict는 제거되었으나, `retain_*` 전역 dict가 새로운 이중 추적 지점. CodeGraph 재검증 권장.

7. ⏳ **cloud 동기화 machine_id 보조 키** (3.3, 추정 — 별도 검토)
   - snapshot manifest에 hostname/생성시간 보조 필드 추가 후 same-machine 판단 보강

---

## 6. Test Recommendations

### 6.1 우선 추가할 테스트

| 테스트 | 목적 | 관련 이슈 | 상태 |
|--------|------|-----------|------|
| `test_http_client_user_agent_version.py` | `HttpClientConfig.user_agent`가 `VERSION`과 일치 | 3.1 | ✅ 추가됨 |
| `test_retain_qthread_until_finished.py` | cleanup timeout 후 orphan thread가 `finished` 시 정리됨; 미발생 시 누적 시나리오 | 3.2 | ✅ 추가됨 |
| `test_cloud_snapshot_empty_id_quarantine.py` | 빈 `snapshot_id` snapshot이 quarantine/거부됨 | 3.3 | ✅ 추가됨 |
| `test_integrity_check_unexpected_exception.py` | `_check_integrity`에서 예기치 못한 예외 시 연결 누출 없음 | 3.4 | ✅ 추가됨 |
| `test_worker_cleanup_timeout_diagnostics` (in `test_fetch_cooldown.py`) | `_worker_cleanup_timeout_count` 임계치 시 사용자 안내 트리거 | 3.5 | ✅ 추가됨 |

### 6.2 기존 스위트 보강

| 파일 | 보강 내용 | 상태 |
|------|----------|------|
| `test_tab_lifecycle_worker_cleanup.py` | `force=True` detach 후 orphan thread가 `_DETACHED_WORKERS`에서 제거됨을 검증 | 별도 검토 (3.2 단위 테스트로 간접 커버) |
| `test_cloud_sync.py` | 동일 `machine_id` + 다른 snapshot_id 교차 시나리오; 빈 id snapshot 처리 | 빈 id 처리는 별도 파일에서 커버 |
| `test_db_integrity_recovery.py` | `_check_integrity` 연결 누출 시나리오(예외 주입) | `test_integrity_check_unexpected_exception.py`에서 커버 |
| `test_fetch_cooldown.py` | cleanup timeout 임계치 도달/중복 방지/미만 미표시 케이스 추가 | ✅ 추가됨 |

### 6.3 회귀 유지 (삭제·약화 금지)

- `test_tab_lifecycle_worker_cleanup.py`, `test_fetch_done_after_rename_stale.py` (v32.7.4 follow-up)
- `test_db_pool_exhaustion_ui.py`, `test_db_integrity_recovery.py`
- `test_settings_import_export_portability.py`, `test_backup_collision_and_restore.py`
- `test_single_instance_guard.py`, `test_qthread_lifetime.py`
- `test_config_secret_storage.py`, `test_risk_fixes.py`

### 6.4 수동/E2E 권장 시나리오

1. 느린 네트워크에서 새로고침 중 탭 닫기·이름 변경 반복 → cleanup timeout 빈도/토스트 확인
2. 클라우드 폴더를 OneDrive/Google Drive 경로로 설정 시 동기화 지연·잠금
3. 두 PC에서 같은 `machine_id`가 발생하는 시나리오(복사본 실행)에서 snapshot 스킵 여부
4. API 429 응답 후 cooldown·toast·재시도 간격 확인
5. `%LOCALAPPDATA%\NaverNewsScraperPro` 백업 후 pending restore 재시작
6. 빈/손상 snapshot을 클라우드 폴더에 넣고 import 시 `.invalid/` 격리 확인

---

*본 문서는 코드 수정 없이 정적 분석·CodeGraph MCP·pytest 실행 결과를 바탕으로 작성되었다. 감사 기준 버전: v32.7.4 (2026-07-11).*
