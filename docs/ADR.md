# Architecture Decision Records (ADR)

## 철학
- **상태 기반 협업 (State-based Collaboration):** AI 에이전트 간의 소통은 대화 로그보다 구조화된 파일 상태를 우선한다.
- **최소 의존성 (Minimal Dependency):** 특정 벤더 도구에 종속되지 않는 범용 기술(Python, Markdown, JSON)을 사용하여 환경 이식성을 높인다.
- **결정의 가시성 (Decision Traceability):** 중요한 작업 결정은 task에 남긴다. 장기적으로 유효한 아키텍처 결정만 ADR에 기록하며 같은 내용을 중복 관리하지 않는다.

---

### ADR-001: 범용 하네스 전환 (Harness Generalization)
**결정**: 기존 Claude 전용 하네스 인프라를 Gemini, Codex, Kimi 등을 지원하는 범용 인프라로 전환한다.
**이유**: 단일 에이전트의 한계를 극복하고, 각 상황에 맞는 최적의 AI 모델을 선택하여 프로젝트를 완수하기 위함이다.
**트레이드오프**: 에이전트별 특성을 100% 활용하는 최적화 대신 공통 분모를 취하는 범용 인터페이스를 유지해야 한다.

### ADR-002: 계약 우선 세션 연속성 (Contract-first Session Continuity)
상태: ADR-004로 기본 정책 대체. 기존 phase 호환 이력.
**결정**: 세션 간 상태 공유는 `stepN-output.json` handoff 대신 `module-map.json`, `phases/baselines/{phase-dir}.json`, public contract를 기본 입력으로 사용한다.
**이유**: handoff 파일 작성·읽기에 소모되는 토큰과 에너지를 줄이고, 이미 git과 baseline이 커버하지 않는 정보가 없음을 확인했기 때문이다.
**트레이드오프**: 세션이 step 중간에 중단된 경우 복구 수단이 git log와 index.json 상태뿐이므로, step이 원자 단위로 완결되는 하네스 규칙을 더 엄격히 지켜야 한다.

### ADR-003: 계약 우선 모듈 경계 (Contract-first Module Boundaries)
상태: ADR-004로 기본 정책 대체. 기존 phase 호환 이력.
**결정**: 후속 step은 이전 step의 구현 전체가 아니라 `module-map.json`, phase baseline, public contract를 우선 입력으로 사용한다. 이전 구현 수정이 필요하면 현재 step에 섞지 않고 `blocking-fix`, `contract-change`, `module-fix`, `backlog-fix` step으로 승격한다.
**이유**: 매 step마다 이전 구현 전체를 다시 읽는 토큰 낭비를 줄이면서도, contract test와 integration step을 통해 결과물 품질을 유지하기 위함이다.
**트레이드오프**: Step 0에서 모듈 경계와 contract를 더 신중하게 설계해야 하며, contract가 틀린 경우 별도 fix/change step이 추가된다.


### ADR-004: Lightweight task records (2026-10-04)
**결정**: 기본 흐름을 짧은 프로젝트 규칙과 작업당 하나의 Markdown 기록으로 전환한다.
**이유**: 실행·계획·검증·컨텍스트 관리의 상당 부분은 각 에이전트가 제공한다. 중복 상태와 계약 문서 유지 비용을 줄인다.
**대체**: ADR-002/003의 contract-first 읽기·별도 fix step 의무는 기본 규칙에서 해제한다. 코드의 공개 계약을 우선하며 관련 구현을 필요한 만큼 읽는다.
**호환**: 기존 phases와 선택적 배치 도구는 유지한다. 모듈 페르소나·registry·baseline·manifest는 새 작업의 필수 구성이 아니다.
**Hooks**: 잘못된 환경 변수 기반 차단과 매 응답 종료 전체 검증을 제거한다. 각 도구의 permissions/sandbox와 명시적 검증을 사용한다.

### ADR-005: 설계 자율성과 실행 근거 (2026-10-04)
**결정**: 모델이 작업에 맞게 설계·구현 단위를 정하며, 하네스는 단일 기록과 검증 근거·실패 복구를 제공한다.
**배치**: 정상 종료·완료 상태·검증 근거를 함께 확인한다. 선택적 checks는 실행기가 수행하며 에이전트가 약화할 수 없다. 재시도는 일시적 오류 또는 코드 변경 진전이 있을 때만 상한 안에서 수행한다.
**컨텍스트**: 기본 CLI에는 프로젝트 지침 위치와 필요한 의존 step을 전달한다. 전체 manifest와 누적 요약을 매번 주입하지 않는다. 자동 로딩이 없는 백엔드에는 inline 규칙을 지원한다.
**트레이드오프**: 기존 완료 이력은 보존하지만 새로 실행하는 legacy step에는 검증 근거가 필요하다. LLM의 자체 기록과 독립 checks를 구분하며 실제 모델 품질은 별도 평가한다.


## ADR-006: 큰 작업의 명시적 실행 단위 (ADR-007로 실행 방식 대체)

단일 작업 기록만으로는 모델이 전체 기능을 한 호출에서 처리할 수 있어 검증 경계가 약했다.
가벼운 기록 형식은 유지하되 harness-plan 블록에 범위·완료 조건·의존 관계·checks를 두고
새 TaskExecutor가 단위별 독립 호출과 검증을 수행한다. 마지막 통합 단위가 전체 결과를 확인한다.
ADR-004의 큰 작업 실행 방식을 보완한다. 작은 수정은 직접 처리하며 기존 phase 데이터와 도구는 보존한다.
모델은 설계와 분해를 판단하고 실행기는 계획 축소·단위 건너뛰기·미검증 완료를 막는다.
자동 커밋은 하지 않으며 기존 검증 실행 로직을 공유하여 중복 구현을 줄인다.


## ADR-007: 현재 도구 세션에서 단위별 개발

사용자는 현재 Claude·Codex에서 하네스를 요청하며 별도 CLI 실행을 원하지 않는다.
ADR-006의 단위 분해·검증 경계는 유지하고 단위별 별도 모델 호출은 제거한다.
TaskExecutor/execute_task.py와 전용 테스트를 제거했으며 task 스캐폴드는 일반 Markdown 문서만 생성한다.
현재 세션의 내장 루프가 각 단위를 구현·검증하고 결과를 기록한 뒤 후속 단위를 수행한다.
외부 실행기의 강제 게이트나 독립 검증으로 표현하지 않는다. 모델 내부 수정 루프와 이중으로 재시도하지 않는다.
기존 task/phase 기록은 보존하고 legacy 배치 도구는 명시적으로 선택한 경우만 사용한다.
