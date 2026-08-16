# Project Audit

## 1. Executive Summary

이 감사는 최근 추가된 GitHub Release 기반 자동 업데이트 기능을 중심으로,
프로젝트의 기존 실행·종료·런타임 데이터 구조와의 연결을 검토한 결과다.

전체 위험도는 **High**다. 서명된 매니페스트, HTTPS, 파일 크기 및 SHA-256
재검증을 갖춘 다운로드 경로는 적절하다. 그러나 업데이트 설치를 시작할 때
`QApplication.quit()`으로 이벤트 루프를 직접 종료해 기존의 창 종료 정리 경로를
우회한다. 활성 fetch, export, FTS backfill, DB 연결이 남은 상태에서 실행 파일
교체 helper가 동작할 수 있어, 기존 앱이 보장하는 안전한 종료 계약과 맞지 않는다.

또한 helper 프로세스의 설치 실패·롤백 결과를 다음 실행에서 확인하거나 사용자에게
표시하는 경로가 없다. 설치에 실패해도 앱은 이미 종료되어 있어 사용자는 원인을
확인하기 어렵다. 실제 EXE 교체·롤백·재시작은 테스트되지 않았고, helper 파일의
정리 및 실패 복구도 누락되어 있다.

### Remediation Status (2026-08-16)

This audit snapshot has been remediated. Update installation now uses the
existing `real_quit()` shutdown path, records helper outcomes for display on the
next start, and cleans stale staged/helper artifacts. The repository signing
secret and tag-based signed-release workflow are also configured. Remaining
items in section 4 are explicitly marked as assumptions for future operations.

## 2. Project Understanding

### 목적 및 규칙

README와 CLAUDE 안내에 따르면 이 프로젝트는 PyQt6 데스크톱 뉴스 관리 앱이다.
NAVER API HUB 검색 결과를 로컬 SQLite DB에 저장하고, 탭별 검색·필터·읽음·북마크·
백업·클라우드 동기화를 제공한다. 주요 규칙은 런타임 DB/설정/백업을 패키지에서
분리하고, DB 오류를 명시적 오류 타입으로 드러내며, 비동기 worker를 안전하게
정리하는 것이다.

### 주요 실행 흐름

CodeGraph 분석 결과의 주요 연결은 다음과 같다.

```text
news_scraper_pro.py
  ├─ handle_update_helper_args()  # --smoke / --apply-update
  └─ core.bootstrap.main()
       └─ MainApp
            ├─ 기존 종료 경로: closeEvent() → _perform_real_close()
            └─ 업데이트 UI: check_for_updates()
                 → download_release_manifest()
                 → verify_release_manifest()
                 → prepare_staged_update()
                 → launch_update_helper()
                 → real_quit() → closeEvent() → _perform_real_close()

별도 helper
  → _wait_for_parent()
  → apply_staged_update()
  → 새 EXE --smoke 실행
  → 새 EXE 재시작 또는 backup 롤백
```

`RuntimePaths`는 기본적으로 사용자 데이터 디렉터리를 설치 폴더와 분리한다.
업데이트 staging은 그 데이터 디렉터리의 `updates/` 아래에 생성되므로, 정상적인
업데이트는 DB·설정·백업 파일을 직접 교체하지 않는다.

## 3. High-Risk Issues

### 1. 업데이트 설치가 기존 안전 종료 경로를 우회함

* 위치: `ui/main_window_update.py::_on_update_downloaded`, `ui/_main_window_tray.py::_perform_real_close`
* 문제: 검증 완료 뒤 `launch_update_helper()` 직후 `QApplication.quit()`을 호출한다. 창의 `close()` 또는 `real_quit()`을 호출하지 않으므로 `closeEvent()`와 `_perform_real_close()`가 수행하는 타이머 정지, 탭 정리, fetch/export/FTS worker 중단, 설정 저장, DB close가 보장되지 않는다.
* 영향: 업데이트 중 활성 작업이 있으면 SQLite write 또는 설정 저장이 중간에 끊길 수 있고, helper는 최대 30초 동안 기존 프로세스 종료를 기다린 뒤 실패한다. 사용자는 업데이트가 시작된 것으로 보지만 실제 설치가 진행되지 않을 수 있다.
* 근거: CodeGraph상 `_perform_real_close()`는 worker 정리와 `db.close()`를 수행하지만, 업데이트 흐름의 129행은 이를 거치지 않고 `QApplication.quit()`만 호출한다.
* 권장 수정 방향: helper를 시작하기 전 공용의 “업데이트 종료” 경로를 만들고, `close()`를 통해 기존 종료 정리를 실행한다. 활성 worker를 정해진 시간 내 정리하지 못하면 helper를 실행하지 말고 staged 파일을 보존/정리하며 사용자에게 취소 이유를 알려야 한다.
* 우선순위: High

### 2. 설치 helper의 실패·롤백 결과가 유실됨

* 위치: `core/update_installer.py::handle_update_helper_args`, `apply_staged_update`, `ui/main_window_update.py::_on_update_downloaded`
* 문제: helper는 예외를 잡아 단순히 종료 코드 `1`만 반환한다. 결과 파일, 다음 시작 시의 상태 확인, 롤백 알림 또는 로그 기록이 없다. helper가 부모 앱 종료 후 실행되므로 UI가 그 종료 코드를 받을 수도 없다.
* 영향: 권한, 파일 잠금, 30초 종료 timeout, smoke 실행 실패, 롤백 실패를 사용자가 구분할 수 없다. 업데이트가 실패한 뒤 이전 버전이 다시 열리지 않는 상황에서도 지원·진단이 어렵다.
* 근거: `handle_update_helper_args()` 119~123행은 모든 예외를 무시하고 `1`을 반환한다. 호출 측은 helper의 `Popen` 성공만 확인한 뒤 앱을 종료한다.
* 권장 수정 방향: staging 디렉터리에 원자적으로 결과 JSON을 기록하고, 다음 앱 시작 시 이를 소비하여 성공·롤백·실패와 상세 오류를 표시한다. rollback 자체 실패는 별도 로그와 수동 복구 안내를 남겨야 한다.
* 우선순위: High

### 3. helper와 backup 파일이 누적될 수 있음

* 위치: `core/update_installer.py::launch_update_helper`, `apply_staged_update`
* 문제: 실행 중인 helper를 `updates/update-helper-<uuid>.exe`로 복사하지만 성공·실패 어느 경로에서도 helper 자신의 삭제 또는 차기 실행 시 정리가 없다. helper 시작 실패 시에도 이미 복사한 helper는 정리되지 않는다. backup은 일부 개수만 유지하지만 helper는 유지 정책이 없다.
* 영향: one-file PyInstaller EXE가 큰 경우 업데이트마다 수십 MB가 사용자 데이터 폴더에 누적될 수 있다. 장기간 자동 업데이트 사용 시 디스크 부족과 실패 확률 상승으로 이어질 수 있다.
* 근거: helper 생성은 98~101행에 있고, cleanup은 `target.name.v*.bak`만 대상으로 한다(92~94행).
* 권장 수정 방향: helper는 결과 기록 뒤 차기 앱 시작에서 안전하게 삭제하거나, 오래된 `update-helper-*.exe`, stale staged EXE, 오래된 결과 파일을 보수적으로 정리하는 cleanup 정책을 둔다. `Popen` 실패 시 즉시 helper도 제거한다.
* 우선순위: Medium

### 4. update worker가 창 종료 후 삭제된 Qt 객체에 emit할 수 있음

* 위치: `ui/main_window_update.py::check_for_updates`, `_download_update`, `_UpdateBridge`
* 문제: 일반 Python daemon thread가 네트워크 작업 후 `self._update_bridge`에 직접 signal을 emit한다. 사용자가 확인/다운로드 중 앱을 닫으면 bridge QObject가 이미 삭제될 수 있다. 성공 emit이 실패하면 except가 다시 같은 삭제된 객체에 emit하므로 thread 예외가 남을 수 있다.
* 영향: 종료 시 비결정적 예외 로그, UI 객체 수명과 thread 수명의 경합, 다음 업데이트 상태의 진단 어려움이 발생할 수 있다.
* 근거: 48~60행 및 100~107행의 daemon thread에는 취소 token, QObject 파괴 검사, worker join/retention이 없다. 기존 QThread worker lifecycle과도 별도 체계다.
* 권장 수정 방향: QThread/Qt worker 또는 취소 가능한 worker abstraction을 사용하고, 종료 시 update 작업을 취소·대기한다. emit 전에 QObject 유효성을 보장하거나 결과 전달 객체를 app lifetime에 맞춰 관리한다.
* 우선순위: Medium

### 5. 매니페스트 형식 오류와 installer 경로의 부정 입력 테스트가 부족함

* 위치: `core/update_manifest.py::verify_release_manifest`, `core/update_installer.py::handle_update_helper_args`, `tests/test_update_manifest.py`
* 문제: 현재 테스트는 정상 서명, tamper, 동일 버전 세 경우만 검증한다. JSON root가 list인 경우, payload 타입 오류, 만료·크기·URL 제한, redirect, 다운로드 중단, helper 인자 조작, 교체/rollback/smoke 실패는 테스트되지 않는다.
* 영향: release 인프라의 실수나 네트워크 오류가 사용자 메시지 대신 예기치 않은 예외로 이어질 가능성이 있다. 특히 실제 EXE 교체 계약은 회귀가 발생해도 탐지되지 않는다.
* 근거: CodeGraph의 blast radius는 `launch_update_helper`, `apply_staged_update`, `handle_update_helper_args`에 covering test가 없다고 표시한다.
* 권장 수정 방향: 네트워크·파일시스템·subprocess를 주입 가능한 함수로 분리하고, 임시 파일 기반의 성공/롤백/경로 검증 테스트와 매니페스트 부정 입력 parameterized test를 추가한다.
* 우선순위: Medium

### 6. 문서와 활성 Spec Kit 포인터가 현재 구현과 일치하지 않음

* 위치: `claude.md`의 Spec Kit 상태, `.specify/feature.json`, `README.md`
* 문제: CLAUDE 안내는 활성 기능을 `specs/001-news-tabsearch-user-readme`로 설명하지만 실제 포인터는 `specs/002-github-release-updates`다. README는 `cryptography` 설치만 언급하고 사용자용 업데이트 버튼·동작·실패 시 GitHub Release 수동 설치 경로를 설명하지 않는다.
* 영향: 다음 구현자가 잘못된 feature artifacts를 읽을 수 있고, 사용자는 새 업데이트 기능의 범위와 복구 방법을 알기 어렵다.
* 근거: 파일의 명시적 active feature 경로가 서로 다르며, README의 기능/FAQ에는 GitHub Release updater 설명이 없다.
* 권장 수정 방향: CLAUDE의 활성 feature·산출물 상태를 갱신하고 README에 Windows 지원 범위, `⬆` 버튼, 업데이트 중 종료 동작, 수동 다운로드 fallback을 추가한다.
* 우선순위: Medium

## 4. Potential Functional Gaps

다음은 코드상 명백한 결함이 아니라, 운영 전에 확인하거나 보완할 가능성이 높은 항목이다.

1. **[추정] GitHub Release 발행 자동화 부재**: 현재는 수동으로 EXE 업로드, 매니페스트 생성, main 브랜치 commit을 해야 한다. 업로드 순서가 어긋나면 서명된 매니페스트가 아직 존재하지 않는 asset을 가리킬 수 있다. CI workflow로 asset 업로드와 매니페스트 publish 순서를 원자적으로 관리하는 방안을 검토할 필요가 있다.
2. **[추정] 코드 서명/SmartScreen 대응**: 매니페스트 서명은 updater 신뢰성을 제공하지만 Windows Authenticode 서명이나 SmartScreen 평판과는 별개다. 배포 대상이 일반 사용자라면 EXE 코드 서명과 다운로드 안내가 필요할 수 있다.
3. **[추정] 설치 권한 UX**: 설치 폴더가 쓰기 불가한 위치(예: Program Files)면 `os.replace`가 실패한다. 현 설계는 다음 시작에서만 결과 확인이 가능하도록 보완되어야 하며, 별도 설치 위치 안내가 필요할 수 있다.
4. **[추정] 프록시/기업망 환경**: stdlib `urlopen` 경로의 프록시·TLS 정책·인증 실패를 사용자 친화적으로 구분하지 않는다. 일반 API 통신과 다른 네트워크 설정을 쓰는지 운영 환경에서 확인할 필요가 있다.

## 5. Recommended Fix Plan

### 1단계: 즉시 수정

1. 업데이트 설치 전 기존의 안전 종료 경로를 반드시 통과하도록 변경한다. worker 정리가 실패하면 업데이트를 연기한다.
2. helper의 applied/rolled_back/failed 결과를 원자적 JSON으로 기록하고, 다음 시작에 표시한다.
3. helper 실행·교체·smoke·rollback 실패를 구분해 로그와 사용자 fallback(GitHub Release 페이지)을 제공한다.

### 2단계: 안정성 개선

1. update check/download를 종료 가능한 Qt worker로 전환하고 앱 종료 시 정리한다.
2. stale staged EXE, helper EXE, 오래된 backup을 보수적으로 정리한다.
3. 실제 파일 교체 성공·rollback·권한 실패·parent timeout·다운로드 중단을 검증하는 테스트를 추가한다.
4. 매니페스트 parser의 모든 부정 형식과 HTTPS redirect/크기 제한을 테스트한다.

### 3단계: 구조 및 운영 개선

1. 릴리즈 asset 업로드와 매니페스트 생성·publish를 CI로 자동화한다.
2. updater의 상태·결과·cleanup을 독립된 `update_state` 모듈로 분리한다.
3. README와 CLAUDE의 업데이트 계약, 지원 OS, 수동 복구 절차, 활성 Spec Kit 정보를 동기화한다.

## 6. Test Recommendations

1. `test_update_install_requests_graceful_shutdown`: 활성 fetch/export/FTS worker가 있을 때 update install이 기존 종료 정리를 완료하거나 설치를 중단하는지 검증한다.
2. `test_update_result_is_consumed_on_next_start`: helper의 applied, rolled_back, failed 결과 파일이 한 번만 읽히고 적절한 UI/로그 메시지로 변환되는지 검증한다.
3. `test_apply_staged_update_rolls_back_on_smoke_failure`: 임시 target/staged/backup과 주입된 smoke runner로 원본이 정확히 복원되는지 검증한다.
4. `test_apply_staged_update_rejects_escape_or_duplicate_paths`: target, staged, backup이 동일하거나 install directory 규칙을 벗어나는 모든 경우를 거부하는지 검증한다.
5. `test_update_helper_cleanup`: helper Popen 실패, 성공 후 다음 앱 시작, stale helper 파일이 각각 올바르게 정리되는지 검증한다.
6. `test_update_worker_close_race`: 확인/다운로드 중 창 종료 시 deleted QObject emit, unhandled thread exception, 남은 thread가 없는지 검증한다.
7. `test_manifest_rejects_malformed_documents`: list root, missing/non-object payload, 만료, 비HTTPS URL, 과대 size, 잘못된 base64/서명, 현재 이하 버전을 parameterized로 검증한다.
8. Windows 패키징 smoke test: PyInstaller one-file 산출물에 `cryptography` Ed25519 모듈이 포함되고 `--smoke`와 `--apply-update` 인자 분기가 GUI를 띄우지 않는지 CI에서 확인한다.
