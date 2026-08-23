# Feature Specification: 감사 후속 안정성 강화

**Feature Branch**: `main`

**Created**: 2026-08-23

**Status**: Approved

**Input**: User description: "PROJECT_AUDIT.md에 제안된 모든 개선 및 수정을 수행한다."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - 신뢰할 수 있는 클라우드 동기화 (Priority: P1)

여러 PC에서 뉴스를 동기화하는 사용자는 일시적인 로컬 오류가 발생해도 정상 스냅샷이 손상 파일로 오인되어 사라지지 않고, 다음 동기화에서 자동으로 재시도되기를 원한다.

**Why this priority**: 원격 변경 누락은 여러 PC의 읽음·북마크·메모·삭제 상태 일관성을 깨뜨리며 사용자가 알아채기 어렵다.

**Independent Test**: 유효한 스냅샷 병합에 일시적 오류를 주입한 뒤 원본이 유지되고 다음 실행에서 성공적으로 병합되는지 확인한다.

**Acceptance Scenarios**:

1. **Given** 구조와 무결성이 유효한 스냅샷, **When** 로컬 DB 잠금 또는 저장 공간 오류로 병합이 실패하면, **Then** 스냅샷은 격리되지 않고 retryable 상태로 남는다.
2. **Given** manifest 누락, 위험 경로 또는 크기 제한 위반 스냅샷, **When** 선택 또는 추출하면, **Then** 해당 파일은 이유와 함께 격리된다.
3. **Given** 격리된 스냅샷, **When** 사용자가 관리 화면에서 확인하면, **Then** 이유를 보고 재검증·복구 또는 삭제할 수 있다.

---

### User Story 2 - 배타적인 데이터 유지보수 (Priority: P1)

사용자는 전체 삭제, 최적화, CSV 가져오기, 일괄 읽음, 클라우드 병합이 진행 중 fetch와 겹치지 않아 예측 가능한 최종 데이터 상태를 얻기를 원한다.

**Why this priority**: 삭제 직후 재삽입이나 잠금 실패는 사용자의 명시적 유지보수 결과를 무효화할 수 있다.

**Independent Test**: DB 저장 단계에서 멈춘 fetch가 있는 동안 유지보수를 요청해 작업이 거부되고, fetch 종료 후에만 시작되는지 확인한다.

**Acceptance Scenarios**:

1. **Given** 종료되지 않은 DB-writing fetch, **When** 유지보수를 요청하면, **Then** 작업은 시작되지 않고 사용자는 재시도 안내를 받는다.
2. **Given** 네트워크 대기 중인 fetch가 취소되어 실제 종료됨, **When** 유지보수를 요청하면, **Then** 작업은 정상 시작된다.
3. **Given** 앱 종료 상황, **When** worker가 timeout되면, **Then** 종료 정책은 유지보수의 배타성 판정과 구분되어 처리된다.

---

### User Story 3 - 안전하고 설명 가능한 데이터 이동 (Priority: P1)

사용자는 뉴스 데이터를 CSV로 내보내고 다시 가져올 때 스프레드시트 수식 위험 없이 원문 의미를 보존하고, 중단·실패 시 어디까지 반영됐는지 알기를 원한다.

**Why this priority**: 외부 뉴스 문자열은 신뢰 경계 밖이며, 부분 적용을 숨기면 데이터 상태를 오판할 수 있다.

**Independent Test**: 위험 수식 prefix를 포함한 항목을 CSV로 내보내 안전하게 열리는지 확인하고, 가져오기 중 오류를 주입해 적용·미변경·누락·실패 행 수가 보고되는지 확인한다.

**Acceptance Scenarios**:

1. **Given** 수식 prefix 또는 선행 제어문자로 시작하는 cell, **When** CSV로 내보내면, **Then** 스프레드시트가 수식으로 평가하지 않는 형태로 저장된다.
2. **Given** 값이 이미 같은 기존 기사와 존재하지 않는 기사, **When** CSV를 가져오면, **Then** 미변경과 누락이 구분되어 보고된다.
3. **Given** 가져오기 중 오류 또는 취소, **When** 작업이 종료되면, **Then** 이미 적용된 행 수와 마지막 처리 위치가 사용자에게 제공된다.

---

### User Story 4 - 재현 가능한 설치와 정확한 안내 (Priority: P2)

개발자와 운영자는 검증된 의존성 조합으로 앱과 테스트를 재현하고, 문서에서 실제 파일명과 활성 명세를 정확히 찾기를 원한다.

**Why this priority**: 재현 불가능한 GUI 환경과 잘못된 경로 안내는 진단·배포 신뢰도를 낮춘다.

**Independent Test**: 깨끗한 지원 Windows 환경에서 선언된 의존성을 설치해 전체 정적 검사·테스트·패키지 smoke를 수행하고 문서 경로를 자동 검증한다.

**Acceptance Scenarios**:

1. **Given** 깨끗한 지원 환경, **When** dependency 선언으로 설치하면, **Then** QtNetwork를 포함한 entrypoint import가 성공한다.
2. **Given** 사용자 문서, **When** runtime 파일 위치를 확인하면, **Then** 실제 생성 파일명과 일치한다.
3. **Given** case-sensitive checkout, **When** 프로젝트 가이드를 열면, **Then** 문서와 활성 feature 포인터가 유효하다.

### Edge Cases

- cloud ZIP은 유효하지만 DB lock, disk full, permission error 또는 취소가 발생한다.
- 이미 격리된 파일과 같은 이름의 파일을 복구하려 한다.
- worker가 network wait, retry sleep, response parsing, DB transaction 각각의 단계에서 취소된다.
- CSV cell 앞에 공백, tab, CR/LF가 있고 그 뒤에 수식 prefix가 온다.
- CSV import 행에 bookmark만, note만, 둘 다 또는 알려지지 않은 link가 있다.
- 의존성 설치 환경의 Python/CPU architecture가 지원 범위를 벗어난다.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: 시스템은 cloud snapshot 구조·무결성 오류와 로컬의 일시적 병합 오류를 구분해야 한다.
- **FR-002**: 일시적 오류로 실패한 유효 snapshot은 원위치에 남아 다음 cycle에서 재시도되어야 한다.
- **FR-003**: 손상 또는 정책 위반 snapshot만 이유 기록과 함께 격리되어야 한다.
- **FR-004**: 사용자는 격리 snapshot 목록, 이유, 재검증 결과를 확인하고 복구 또는 삭제할 수 있어야 한다.
- **FR-005**: DB를 변경할 수 있는 fetch가 실제 종료되기 전에는 maintenance 작업을 시작하면 안 된다.
- **FR-006**: worker cleanup 결과는 실제 종료와 단순 분리를 구분해야 한다.
- **FR-007**: CSV export는 spreadsheet formula로 평가될 수 있는 모든 신뢰되지 않은 cell을 안전하게 중화해야 한다.
- **FR-008**: CSV import는 updated, unchanged, missing, failed, processed 수와 마지막 처리 행을 구분해 반환해야 한다.
- **FR-009**: CSV import 중 오류·취소의 부분 반영 정책을 UI와 문서에서 명시해야 한다.
- **FR-010**: 프로젝트는 검증된 runtime dependency와 지원 Python 범위를 선언해야 한다.
- **FR-011**: README의 runtime 파일명, 활성 Spec Kit 포인터, guide filename case는 실제 저장소와 일치해야 한다.
- **FR-012**: cloud, maintenance, CSV, dependency/document contract에 회귀 테스트가 있어야 한다.
- **FR-013**: 기존 public facade import, ApiWorker payload, canonical query, backup containment, note 길이 계약을 깨뜨리면 안 된다.

### Key Entities

- **Cloud Snapshot Candidate**: 파일 경로, snapshot ID, 검증 상태, 오류 분류, retry 가능 여부를 가진 동기화 입력.
- **Quarantine Entry**: 격리 파일, 원래 이름, 이유, 격리 시각, 재검증 상태를 가진 복구 가능한 항목.
- **Worker Cleanup Outcome**: 실제 종료, 이미 종료, 계속 실행 중인 분리, 실패를 구분하는 결과.
- **CSV Import Result**: processed, updated, unchanged, missing, failed, truncated notes, last row 정보를 가진 작업 결과.
- **Dependency Contract**: 지원 Python 범위와 검증된 runtime package 조합.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 유효 snapshot의 일시적 DB 오류 시 100% 원본이 유지되고 다음 성공 cycle에서 병합된다.
- **SC-002**: malformed/oversized/path-unsafe snapshot의 100%가 이유와 함께 격리된다.
- **SC-003**: DB-writing worker가 종료되지 않은 모든 테스트에서 maintenance 시작률은 0%다.
- **SC-004**: 위험 CSV prefix 테스트 집합의 100%가 spreadsheet-safe하게 저장된다.
- **SC-005**: CSV import의 정상·미변경·누락·오류·취소 시나리오 모두 처리 결과 합계가 입력 행 수와 일치한다.
- **SC-006**: 검증된 Windows 개발 환경에서 전체 정적 검사와 자동 테스트가 통과하고 entrypoint import가 성공한다.
- **SC-007**: README와 guide의 모든 runtime 파일명·활성 feature 경로가 자동 검사와 일치한다.

## Assumptions

- Windows 10/11이 지원 대상이며 macOS/Linux 제품 지원 확대는 범위 밖이다.
- CSV는 spreadsheet-safe 형식을 기본으로 하며 JSON export는 원문 보존용으로 유지한다.
- cloud transient error는 자동 재시도하되 무한 즉시 retry는 하지 않는다.
- CSV import는 대용량 처리를 위해 행 단위 commit을 유지하고 부분 적용을 명확히 보고한다.
- 기존 `.invalid` 파일은 삭제하지 않고 복구 가능한 상태로 유지한다.
