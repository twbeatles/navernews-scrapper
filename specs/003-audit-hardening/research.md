# Research: 감사 후속 안정성 강화

## R1. Cloud 오류 분류

**Decision**: `CloudSyncError`의 하위 타입으로 snapshot 내용/형식 검증 오류와 runtime/transient 오류를 분리한다. 자동 격리는 전자만 허용한다.

**Rationale**: 현재 manifest/extract와 DB preview/merge가 광범위한 `except Exception` 아래 있어 유효한 원본도 이동된다. 예외 메시지 문자열 분류는 SQLite/OS별 차이 때문에 불안정하다.

**Alternatives rejected**: 모든 `CloudSyncError` 격리, 메시지 prefix 비교, 자동 격리 완전 제거.

## R2. Quarantine lifecycle

**Decision**: `.invalid` 항목을 core API로 열거하고 원래 snapshot 이름과 이유를 metadata에 보존한다. 재검증 성공 후에만 cloud root로 복구하며 충돌 시 덮어쓰지 않는다. 삭제는 명시적 사용자 확인 후 실행한다.

## R3. Worker cleanup과 maintenance

**Decision**: `finished`, `already_finished`, `detached_running`, `failed`를 구분하는 outcome을 추가한다. 기존 bool API는 호환성을 위해 유지하되 maintenance는 실제 종료 상태만 통과시킨다.

**Rationale**: QThread 객체를 registry/UI에서 분리하는 것과 DB-writing thread가 종료되는 것은 다른 상태다.

## R4. CSV formula neutralization

**Decision**: spreadsheet에서 formula로 해석할 수 있는 사용자 문자열을 apostrophe prefix로 중화한다. 선행 whitespace/control 뒤 위험 문자가 나오는 경우도 포함한다.

**Rationale**: CSV quoting은 formula 실행을 막지 않는다.

## R5. CSV import atomicity and reporting

**Decision**: 링크 존재 확인과 선택된 bookmark/note update를 동일 SQLite transaction에서 수행한다. 각 행 결과를 반환하고 caller가 구조화된 합계를 누적한다.

**Rationale**: 현재 두 mutation 사이 오류가 나면 한 행이 반쪽만 반영되며 `False`가 missing과 unchanged를 모두 의미한다.

## R6. Dependency reproducibility

**Decision**: runtime/build requirements를 분리하고 release CI가 이를 설치한다. Python 3.14 Windows를 기준선으로 유지하고 QtNetwork import smoke를 별도 실행한다.

**Rationale**: 무제한 `--upgrade`는 release마다 다른 wheel 조합을 설치한다. 설치 파일과 CI smoke를 함께 계약으로 삼는다.

## R7. External E2E boundary

**Decision**: 실제 NAVER API 호출은 secret이 있는 비-production 환경에서만 opt-in으로 실행한다. 기본 CI에서는 HTTP adapter integration test를 유지한다.

**Rationale**: 공개 CI에서 credential과 rate limit에 의존하는 테스트는 결정적이지 않다.
