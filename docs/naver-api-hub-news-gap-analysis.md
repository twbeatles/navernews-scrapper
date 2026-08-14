# NAVER API HUB 뉴스 검색 — 문서 vs 앱 반영 조사

- **문서**: 뉴스 검색 결과 조회 (`/search/v1/news`)
- **문서 갱신 참고**: 2026-06-25 (사용자 제공 스냅샷)
- **조사일**: 2026-07-16
- **대상 코드**: `core/naver_api.py`, `core/workers_support/api_worker.py`, fetch 페이지네이션, 설정 검증

---

## 결론 요약

**핵심 계약(엔드포인트·헤더·쿼리·item 필드·페이지 한도)은 대체로 잘 반영되어 있습니다.**  
다만 문서에 있는 일부 옵션·메타데이터·운영 정보는 **의도적 생략**이거나 **미반영** 상태입니다.

---

## 이미 잘 맞는 부분

| 문서 | 구현 | 위치 |
|------|------|------|
| `GET /search/v1/news` | API HUB URL 사용 | `core/naver_api.py` |
| 헤더 `X-NCP-APIGW-API-KEY-ID` / `X-NCP-APIGW-API-KEY` | 동일 | `naver_auth_headers()` |
| `query` (UTF-8) | 검색어 전달 (`requests` params) | `api_worker.py` |
| `display` 1~100 | 고정 `100` (상한) | `api_worker.py` |
| `start` 1~1000 | 커서 + `+100`, 1000 초과 차단 | `start.py`, `state.py`, `config.py` |
| `sort` | `date` 고정 (날짜 내림차순) | `api_worker.py` |
| item: `title`, `link`, `originallink`, `description`, `pubDate` | 파싱·저장 경로에 사용 | `api_worker.py` |
| `<b>` 하이라이트 | 제거 후 저장 | `RE_BOLD_TAGS` + `html.unescape` |
| `total` | 더 불러오기/배지에 사용 | finished payload → `completion.py` |
| Search 오류 `errorCode`/`errorMessage` (SE02 등) | 파싱 후 사용자 메시지 | `parse_naver_api_error` |
| 설정 검증 | 동일 URL/헤더 사용 | `_settings_dialog_tasks.py` |

### 페이지네이션 계약

- 한 번에 `display=100`
- 다음 `start = last + 100`
- `start > 1000`이면 중단

→ 이론상 API로 가져올 수 있는 구간(최대 1000건)을 채웁니다.

---

## 미반영 / 부분 반영 항목

### 1. `sort=sim` (정확도 정렬) — 미제공

문서:

- `sim` (기본값, 정확도) | `date` (날짜)

앱:

- 항상 `"sort": "date"`만 사용
- UI/설정에서 정확도 정렬 선택 없음

뉴스 수집 앱 특성상 `date` 고정은 자연스럽지만, **문서 기능 중 하나는 노출하지 않습니다.**

### 2. `format` 파라미터 — 미전송 (실무상 OK)

문서: `json` (기본) | `xml`  
앱: `format` 미지정 → 기본 JSON 사용 가정

의도적으로 JSON만 쓰는 구조라면 문제 없습니다. XML 지원은 필요 없어 보입니다.

### 3. 응답 메타 `lastBuildDate` — 미사용

문서 응답 필드 중 `lastBuildDate`는 파싱·표시·저장하지 않습니다.  
기능 필수값은 아니지만, “검색 결과 생성 시각” 표시/디버깅에는 활용 여지가 있습니다.

### 4. `originallink` — 해석용으로만 사용, 별도 저장 없음

문서:

- `link`: 네이버 뉴스 URL (없으면 원문)
- `originallink`: 원문 URL

앱:

- 링크 결정·언론사 추출에 `originallink` 사용
- DB `news` 스키마에는 `link` 하나만 저장 (`originallink` 컬럼 없음)

그래서:

- 네이버 URL과 원문을 **동시에** 보관·표시하지는 못함
- “원문 바로가기 + 네이버 뉴스 보기” 이중 링크 UX는 문서 모델 대비 약함

문서 스펙 위반은 아니지만, **필드 정보를 전부 보존하지는 않습니다.**

### 5. 하루 호출 한도 25,000회 — 앱에서 미추적

문서:

> 검색 API 하루 호출 한도 25,000회

앱:

- HTTP 429 / rate limit 쿨다운은 있음
- **일일 호출 수 카운트, 잔여 한도 표시, 사전 차단은 없음**

한도 초과 시 서버 오류/제한에 사후 대응하는 수준입니다.

### 6. 오류 코드(SE01~SE06, SE99) — 파싱만, 코드별 UX 없음

`parse_naver_api_error`가 `errorCode`/`errorMessage`를 읽고 그대로 보여줍니다.  
문서의 코드별 원인 가이드(예: SE02 → display 범위 확인)를 앱이 별도로 매핑하진 않습니다.

현재 고정 파라미터(`display=100`, `start` 클램프, `sort=date`) 때문에 SE02/SE03/SE04는 거의 안 나겠지만,  
잘못된 검색어 인코딩(SE06) 등은 일반 HTTP 오류 문구로만 보일 수 있습니다.

### 7. `display` 사용자 설정 — 없음 (의도적일 가능성 큼)

문서 범위 1~100 중 앱은 항상 100.  
효율 측면에서는 합리적이나, “한 번에 더 적게 받기” 같은 옵션은 없습니다.

---

## 의도적으로 문서 기본값과 다른 점

| 항목 | 문서 기본 | 앱 | 평가 |
|------|-----------|-----|------|
| `sort` | `sim` | `date` | 뉴스 최신 수집에 적합, 의도적 선택으로 보임 |
| `display` | `10` | `100` | 상한 활용, 합리적 |
| `format` | `json` | 생략(=json) | 문제 없음 |

---

## 문서 오류 코드 참고 (앱 전용 매핑 없음)

| HTTP | 코드 | 메시지 (요약) | 설명 |
|------|------|---------------|------|
| 400 | `SE01` | Incorrect query request | URL/파라미터 오류 |
| 400 | `SE02` | Invalid display value | `display` 범위 |
| 400 | `SE03` | Invalid start value | `start` 범위 |
| 400 | `SE04` | Invalid sort value | `sort` 오타 |
| 404 | `SE05` | Invalid search api | API URL 오타 |
| 400 | `SE06` | Malformed encoding | 검색어 UTF-8 |
| 500 | `SE99` | System Error | 서버 내부 오류 |

Gateway 공통 오류(401/403 등)는 `format_naver_http_error`에서 auth 안내를 붙입니다.

---

## 우선순위 제안

| 우선순위 | 항목 | 이유 |
|----------|------|------|
| 낮음~중간 | `sort=sim` 옵션 | 문서 기능 중 유일하게 사용자 선택 가능한 정렬이 빠진 상태 |
| 낮음~중간 | `originallink` 별도 저장 | 원문/네이버 URL 이중 보관이 필요할 때 |
| 낮음 | 일 25,000 호출 카운터/안내 | 다탭·자동갱신 시 운영 가시성 |
| 매우 낮음 | `lastBuildDate`, SE 코드별 안내, `format` | 현재 제품 목표에 필수는 아님 |

---

## 한 줄 정리

이 프로그램은 **NAVER API HUB 뉴스 검색의 필수 계약(URL, 인증 헤더, query/display/start, item 필드, total 기반 페이지네이션, 오류 파싱)을 이미 충실히 반영**하고 있습니다.  
문서 대비 빈틈은 주로 **선택 기능(`sort=sim`)**, **원문 링크 보존**, **일일 호출 한도 관리**, **일부 응답 메타/오류 UX 세분화** 쪽입니다.

---

## 관련 코드 경로

| 역할 | 경로 |
|------|------|
| API HUB 상수/헤더/오류 파싱 | `core/naver_api.py` |
| 실제 뉴스 fetch | `core/workers_support/api_worker.py` |
| 더 불러오기 start/total | `ui/main_window_fetch_support/worker_flow_support/` |
| 설정 API 키 검증 | `ui/_settings_dialog_tasks.py` |
| 테스트 | `tests/test_naver_api_hub.py` |
