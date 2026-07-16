# Claude Assistant Guide - 뉴스 스크래퍼 Pro

이 문서는 현재 코드베이스를 기준으로 한 작업 가이드입니다. 과거 날짜별 구현 로그는 유지하지 않습니다.

## 프로젝트 요약

- PyQt6 데스크톱 앱
- **NAVER API HUB** 뉴스 검색 API + 로컬 SQLite DB
- 핵심 진입점: `news_scraper_pro.py`
- 앱 부팅: `core.bootstrap.main()`
- 메인 UI: `ui.main_window.MainApp`
- DB facade: `core.database.DatabaseManager`
- API 연동: `core.naver_api` + `core.workers_support.api_worker.ApiWorker`
- 현재 버전: `core.constants.VERSION`

## 기본 원칙

- root compatibility wrapper와 facade import를 깨지 않습니다.
- 검색 의미는 canonical query / fetch key 기준입니다.
- 사용자-visible 필터 의미를 바꿀 때는 fetch, count, badge, tray, export, archive를 같이 확인합니다.
- FTS hard prefilter는 false negative 방지를 위해 다시 켜지 않습니다.
- DB write/query 실패는 각각 `DatabaseWriteError`, `DatabaseQueryError`로 드러내는 방향을 유지합니다.
- 단일 탭 fetch, 더 불러오기, 순차 fetch는 모두 `fetch_news()`의 API 자격증명 guard를 통과해야 합니다.
- 탭 닫기/이름 변경은 active worker cleanup 실패 시 상태 변경을 진행하지 않습니다.
- 메모는 저장 전 10,000자로 제한하고, import/export 문서 계약과 테스트를 같이 유지합니다.
- destructive backup 경로는 backup root 아래의 단일 이름만 허용합니다.
- 문서는 현재 코드 상태를 우선하고, 오래된 변경 누적 로그를 다시 붙이지 않습니다.
- **네이버 API 호출 URL/헤더는 `core/naver_api.py`에만 둡니다.** `ApiWorker`와 설정 검증이 동일 헬퍼를 사용해야 합니다.
- 레거시 Developers Center (`openapi.naver.com`, `X-Naver-Client-*`) 엔드포인트로 되돌리지 않습니다.

## 현재 구조

```text
core/
  bootstrap.py
  naver_api.py
  database.py
  db_schema_support/
  db_queries_support/
  db_mutations_support/
  workers_support/
  cloud_sync_support/
  backup_support/
  runtime_support/
ui/
  main_window.py
  main_window_support/
  main_window_fetch_support/
  main_window_io_support/
  news_tab.py
  news_tab_support/
  dialogs_support/
tests/
```

## 주요 작업 위치

| 작업 | 위치 |
|---|---|
| API HUB 상수/오류 파싱 | `core/naver_api.py` |
| API fetch | `core/workers_support/api_worker.py` |
| 설정 API 키 검증 | `ui/_settings_dialog_tasks.py` |
| 설정 API UI/도움말 | `ui/_settings_dialog_content.py`, `ui/_settings_dialog_docs.py` |
| DB list/count | `core/db_queries_support/fetch.py` |
| DB upsert | `core/db_mutations_support/news_upsert.py` |
| DBWorker | `core/workers_support/db_worker.py` |
| 탭 로딩 | `ui/news_tab_support/loading_support/db_loading.py` |
| 탭 렌더링 | `ui/news_tab_support/rendering.py` |
| badge/tray | `ui/main_window_support/ui_shell_support/` |
| settings import/export | `ui/main_window_io_support/` |
| cloud sync | `core/cloud_sync_support/`, `core/db_cloud_sync_support/` |
| packaging | `news_scraper_pro.spec` |

## NAVER API HUB 계약

- URL: `https://naverapihub.apigw.ntruss.com/search/v1/news`
- 헤더: `X-NCP-APIGW-API-KEY-ID`, `X-NCP-APIGW-API-KEY`
- config 필드: `client_id` / `client_secret` (이름 유지, 값은 API HUB 키)
- 성공 응답 item 필드: `title`, `link`, `originallink`, `description`, `pubDate` (파싱 유지)
- 오류: Search 평면(`errorCode`/`errorMessage`) + Gateway 중첩(`error.message`) → `parse_naver_api_error`
- 401/403 → `auth_error` kind
- UI/도움말 문구는 개발자센터가 아니라 API HUB 기준으로 유지

## 경로/데이터 정책

- cloud sync folder는 core API에서 빈 값을 거부하고, 상대 경로는 절대 경로로 resolve한 뒤 사용합니다.
- CSV/Markdown export 기본 파일명은 `ValidationUtils.safe_filename_component(...)`로 정규화합니다.
- backup delete/restore/schedule/pending restore는 `core.backup_support.fs._safe_backup_child_dir(...)`를 통해 root containment를 확인합니다.

## 현재 성능 계약

- `upsert_news_detailed(...) -> NewsUpsertResult`는 fetch 저장과 신규 link 산출을 한 경로에서 처리합니다.
- `upsert_news(...) -> tuple[int, int]`는 legacy 공개 API로 유지됩니다.
- `count_news_states(...) -> NewsCountSummary`는 total/unread count를 단일 scope query로 계산합니다.
- `ApiWorker.finished` payload shape는 유지합니다.
- `DBWorker` append는 known total을 재사용합니다.
- 탭 badge는 DB load unread count와 local unread cache를 우선 사용합니다.

## 검증

기본:

```bash
python -m pytest -q
python -m pyright
```

문서/spec 변경:

```bash
python -m pytest tests/test_encoding_smoke.py tests/test_version_history_guard.py tests/test_spec_runtime_tmpdir.py -q
```

API HUB 연동:

```bash
python -m pytest tests/test_naver_api_hub.py tests/test_settings_validation_http_policy.py -q
```

패키징:

```bash
python -m PyInstaller --noconfirm --clean news_scraper_pro.spec
```

## Git/문서 체크리스트

- `.codegraph/`, build, dist, cache, runtime DB/config/log는 커밋하지 않습니다.
- 문서에는 현재 public API와 실제 module 위치만 남깁니다.
- 새 dependency가 생기면 README와 spec hiddenimports/excludes를 같이 확인합니다.
- spec은 `runtime_tmpdir=None`을 유지합니다.
- VERSION 변경 시 `update_history.md`에 `## v{VERSION}` 섹션을 추가합니다.
