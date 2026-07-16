# 뉴스 스크래퍼 Pro v32.7.6

네이버 클라우드 **NAVER API HUB** 뉴스 검색 API를 사용하는 PyQt6 데스크톱 앱입니다. 탭별 검색어, 읽음/북마크/메모/태그, 출처 필터, 자동화 규칙, 백업/복원, 클라우드 스냅샷 동기화를 로컬 SQLite DB 위에서 관리합니다.

이 문서는 현재 코드베이스 상태를 기준으로 유지합니다. 오래된 구현 로그와 날짜별 작업 메모는 Git history를 기준으로 확인합니다.

## 현재 기준

- 플랫폼: Windows 우선, Python 3.14, PyQt6, SQLite, requests
- 뉴스 API: **NAVER API HUB** (`https://naverapihub.apigw.ntruss.com/search/v1/news`)
- 실행 진입점: `news_scraper_pro.py`
- 앱 부팅: `core.bootstrap.main()`
- 메인 UI: `ui.main_window.MainApp`
- DB facade: `core.database.DatabaseManager`
- API 연동 상수/헬퍼: `core.naver_api`
- 패키징: `news_scraper_pro.spec` 기반 PyInstaller onefile
- 기본 검증: `python -m pytest -q`, `python -m pyright`

## API 키 설정 (NAVER API HUB)

v32.7.6부터 레거시 **네이버 개발자센터**(`openapi.naver.com`) 연동은 제거되었습니다. **NAVER API HUB**에서 발급한 키만 사용할 수 있습니다.

### 발급 절차

1. [네이버 클라우드 플랫폼](https://www.ncloud.com/)에 로그인합니다.
2. 콘솔에서 **Application Services → NAVER API HUB** 이용을 신청합니다.
3. **Application 등록** 시 검색 API(뉴스)를 포함합니다.
4. Application **인증 정보**에서 Client ID / Client Secret을 복사합니다.
5. 앱 설정(`Ctrl+,`)에 입력한 뒤 **API 키 검증**을 실행합니다.

참고 문서:

- [NAVER API HUB 사용 가이드](https://guide.ncloud-docs.com/docs/apihub-use)
- [이관 가이드](https://guide.ncloud-docs.com/docs/apihub-migration)
- [뉴스 검색 API](https://api.ncloud-docs.com/docs/naver-api-hub-search-news)
- [제품 소개/요금](https://www.ncloud.com/product/applicationService/naverApiHub)

### 호출 계약 (앱 내부)

| 항목 | 값 |
|---|---|
| URL | `https://naverapihub.apigw.ntruss.com/search/v1/news` |
| Method | `GET` |
| Client ID 헤더 | `X-NCP-APIGW-API-KEY-ID` |
| Client Secret 헤더 | `X-NCP-APIGW-API-KEY` |
| 공통 모듈 | `core/naver_api.py` (`naver_auth_headers`, `parse_naver_api_error`) |
| Fetch | `core/workers_support/api_worker.py` |
| 설정 검증 | `ui/_settings_dialog_tasks.py` |

- 기존 개발자센터 Client ID/Secret은 API HUB에서 **재사용 불가**합니다.
- config 필드 이름(`client_id`, `client_secret`)은 유지하되, 값은 API HUB 신규 키로 교체해야 합니다.
- 검색 API 일 호출 한도(문서 기준 최대 25,000회)와 한시 무료/종량 정책은 NCP 안내를 따릅니다.
- 앱은 호출당 `display=100`, `sort=date`를 사용합니다. 조회 시작 위치 `start`는 1~1000입니다.

## 주요 기능

- 탭 기반 뉴스 검색과 canonical query 기준 중복 탭 방지
- 제외어, 날짜, 텍스트, 읽음, 중복 숨김, 태그, 출처 필터
- 기사 읽음/북마크/메모/태그 관리와 탭 간 상태 동기화
- 전체 아카이브 검색, CSV/Markdown digest 내보내기
- 자동화 규칙: 태그, 북마크, 읽음, 제외, 알림 억제
- 출처 alias, 차단 출처, 선호 출처 필터
- 키워드 그룹, 저장된 검색, 탭별 자동 새로고침 정책
- 설정 export/import, 자동/수동 백업, pending restore
- 로컬 DB + ZIP 스냅샷 기반 클라우드 동기화
- 단일 인스턴스, 트레이, Windows 자동 시작

## 프로젝트 구조

```text
navernews-tabsearch/
├── news_scraper_pro.py          # 실행 진입점 + 공개 re-export
├── news_scraper_pro.spec        # PyInstaller onefile 설정
├── core/                        # DB, workers, config, sync, backup, query parser
│   ├── naver_api.py             # NAVER API HUB URL/헤더/오류 파싱
│   ├── database.py              # DatabaseManager facade
│   ├── workers_support/         # ApiWorker, DBWorker, job workers
│   ├── db_queries_support/      # fetch/count/archive/query helpers
│   ├── db_mutations_support/    # upsert/state/tag/maintenance mutations
│   ├── cloud_sync_support/      # snapshot I/O and import flow
│   └── runtime_support/         # DATA_DIR and legacy runtime migration
├── ui/                          # MainApp, NewsTab, dialogs, styles
│   ├── main_window_support/
│   ├── main_window_fetch_support/
│   ├── main_window_io_support/
│   └── news_tab_support/
├── tests/                       # pytest regression suite
├── database_manager.py          # root compatibility wrapper
├── query_parser.py              # root compatibility wrapper
├── workers.py                   # root compatibility wrapper
└── styles.py                    # root compatibility wrapper
```

Root compatibility wrappers are intentionally kept. New code should prefer `core.*` and `ui.*` imports unless it is maintaining legacy public paths.

## 실행

```bash
pip install PyQt6 requests
python news_scraper_pro.py
```

패키징된 실행 파일이 있으면 `dist/NewsScraperPro_Safe.exe`를 실행합니다.

처음 실행 시 API 키가 없으면 설정 안내가 표시됩니다. NAVER API HUB 키를 입력한 뒤 검증하세요.

## 검증

```bash
python -m pytest -q
python -m pyright
```

문서/인코딩 변경 후에는 아래 smoke test도 같이 확인합니다.

```bash
python -m pytest tests/test_encoding_smoke.py tests/test_version_history_guard.py tests/test_spec_runtime_tmpdir.py -q
```

API HUB 연동 회귀:

```bash
python -m pytest tests/test_naver_api_hub.py tests/test_settings_validation_http_policy.py -q
```

## 빌드

```bash
python -m PyInstaller --noconfirm --clean news_scraper_pro.spec
```

- 산출물: `dist/NewsScraperPro_Safe.exe`
- `news_icon.ico`는 있으면 실행 파일 아이콘으로 사용합니다.
- `runtime_tmpdir`는 고정하지 않고 대상 PC의 기본 임시 폴더를 사용합니다.

## 데이터 위치

기본 런타임 데이터는 `DATA_DIR`에 저장됩니다.

- Windows: `%LOCALAPPDATA%\NaverNewsScraperPro`
- macOS: `~/Library/Application Support/NaverNewsScraperPro`
- Linux: `$XDG_DATA_HOME/NaverNewsScraperPro` 또는 `~/.local/share/NaverNewsScraperPro`
- `NEWS_SCRAPER_DATA_DIR`: 런타임 데이터 위치 강제
- `NEWS_SCRAPER_PORTABLE=1`: 앱 폴더를 런타임 위치로 사용

주요 파일은 `news_scraper_config.json`, `news_database.db`, `news_scraper.log`, `pending_restore.json`, `backups/`, `news_scraper_pro.lock`입니다. 실행 폴더에 남은 레거시 런타임 파일은 시작 시 `DATA_DIR`로 비파괴 마이그레이션됩니다.

## 검색/필터 의미

- 탭 표시명과 관계없이 실제 scope는 `query_key = build_fetch_key(parse_search_query(raw_query))` 기준입니다.
- API query는 양수 키워드를 공백으로 결합하고, 대표 DB keyword는 첫 양수 키워드를 사용합니다.
- 제외어-only 검색은 탭 추가/이름 변경/import에서 차단됩니다.
- `%`, `_`, `\`는 LIKE wildcard가 아니라 literal 문자로 처리합니다.
- 공백으로 나뉜 텍스트 필터는 token-AND 의미입니다.
- FTS schema/backfill은 유지하지만, false negative 방지를 위해 FTS rowid hard prefilter는 사용하지 않습니다.

## DB/Worker 계약

- `DatabaseManager.upsert_news(...) -> tuple[int, int]`는 기존 공개 API로 유지됩니다.
- `DatabaseManager.upsert_news_detailed(...) -> NewsUpsertResult`는 저장과 현재 query scope의 신규 link 계산을 한 경로에서 처리합니다.
- `DatabaseManager.count_news(...) -> int`는 기존 공개 API로 유지됩니다.
- `DatabaseManager.count_news_states(...) -> NewsCountSummary`는 같은 scope의 total/unread count를 단일 쿼리로 계산합니다.
- `ApiWorker.finished` payload shape는 `items`, `new_items`, `new_count`, `total`, `filtered`, `added_count`, `dup_count`를 유지합니다.
- `DBWorker` full reload는 가능하면 `count_news_states(...)`를 사용하고, append는 known total을 재사용합니다.
- 탭 배지는 DB load의 unread count와 NewsTab 로컬 unread cache를 우선 사용해 불필요한 count refresh를 줄입니다.
- 단일 탭 새로고침, 더 불러오기, 순차 새로고침은 모두 `fetch_news()`에서 API 자격증명을 중앙 검증한 뒤 worker를 생성합니다.
- 탭 닫기/이름 변경은 기존 fetch worker 정리가 timeout되면 탭 상태 변경을 보류합니다.
- API HTTP 오류는 Search API 평면 오류(`errorCode`/`errorMessage`)와 API Gateway 중첩 오류(`error.message`)를 `core.naver_api.parse_naver_api_error`로 통일 파싱합니다.
- 401/403은 `auth_error`로 분류해 사용자에게 API HUB 키 확인을 안내합니다.

## 설정 Export/Import

- 현재 export schema는 `1.3`입니다.
- API 자격증명은 export/import와 cloud snapshot settings에서 제외됩니다.
- `automation_rules`와 `publisher_aliases`는 일반 설정 export/import에는 포함되고 cloud snapshot settings에서는 제외됩니다.
- `tabs`, `search_history`, `pagination_state`, `pagination_totals`, `saved_searches`, `tab_refresh_policies`는 canonical query/fetch key 기준으로 정규화됩니다.
- 다른 PC의 export에서 들어온 자동 시작 설정은 로컬 오등록 방지를 위해 안전하게 보정됩니다.
- 메모는 저장 경로와 CSV 가져오기에서 최대 10,000자로 정규화됩니다. 초과분은 잘리고 UI/import 결과에 표시됩니다.
- CSV/Markdown 내보내기 dialog의 기본 파일명은 검색어 원문이 아니라 OS-safe filename component를 사용합니다.

## 클라우드 동기화

클라우드 폴더에는 live SQLite DB를 직접 두지 않고 `news_scraper_sync_*.zip` 스냅샷만 교환합니다. 스냅샷에는 manifest, secret 제거 settings, SQLite backup API로 만든 DB 복사본이 들어갑니다.

동기화 병합은 기사 link와 `(link, query_key)` membership을 union하고, 읽음/북마크/메모/태그/삭제 tombstone은 timestamp 최신값을 따릅니다. 손상되었거나 크기 제한을 넘는 스냅샷은 `.invalid/`로 격리됩니다.

빈 cloud sync folder는 core API에서도 거부됩니다. 상대 경로는 현재 작업 디렉터리 기준 절대 경로로 해석한 뒤 snapshot 경로로 사용합니다.

동일 머신에서 생성된 snapshot(`machine_id` 일치)은 자동으로 병합을 건너뛰고 seen으로 기록됩니다. snapshot manifest의 `snapshot_id`가 비어 있으면 거부되어 병합되지 않습니다.

## 백업/복원 안전 정책

백업 삭제, 즉시 복원, pending restore 예약/적용은 backup name을 단일 디렉터리 이름으로만 허용합니다. 절대 경로, 드라이브 포함 경로, `..`, `/`, `\`가 포함된 이름은 backup root 밖을 가리킬 수 있으므로 거부됩니다.

## 단축키

| 단축키 | 기능 |
|---|---|
| `Ctrl+R` / `F5` | 모든 탭 새로고침 |
| `Ctrl+T` | 새 탭 추가 |
| `Ctrl+W` | 현재 탭 닫기 |
| `Ctrl+F` | 검색/필터 포커스 |
| `Ctrl+S` | CSV 또는 Markdown 내보내기 |
| `Ctrl+Shift+F` | 전체 아카이브 검색 |
| `Ctrl+Shift+T` | 태그 관리자 |
| `Ctrl+Shift+A` | 자동화 규칙 |
| `Ctrl+,` | 설정 |
| `Alt+1~9` | 탭 바로가기 |

## 관련 문서

- `project_structure_analysis.md`: 현재 아키텍처와 변경 진입점
- `claude.md`, `gemini.md`: AI assistant용 작업 가이드
- `update_history.md`: 현재 버전 중심 변경 요약

## 라이선스

MIT License
