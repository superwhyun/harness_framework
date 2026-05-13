# Architecture Decision Records (ADR)

## 철학
- **상태 기반 협업 (State-based Collaboration):** AI 에이전트 간의 소통은 대화 로그보다 구조화된 파일 상태를 우선한다.
- **최소 의존성 (Minimal Dependency):** 특정 벤더 도구에 종속되지 않는 범용 기술(Python, Markdown, JSON)을 사용하여 환경 이식성을 높인다.
- **결정의 가시성 (Decision Traceability):** 모든 작업의 판단 근거를 `ADR`과 `stepN-output.json`에 남겨, 나중에라도 추론이 가능하게 한다.

---

### ADR-001: 범용 하네스 전환 (Harness Generalization)
**결정**: 기존 Claude 전용 하네스 인프라를 Gemini, Codex, Kimi 등을 지원하는 범용 인프라로 전환한다.
**이유**: 단일 에이전트의 한계를 극복하고, 각 상황에 맞는 최적의 AI 모델을 선택하여 프로젝트를 완수하기 위함이다.
**트레이드오프**: 에이전트별 특성을 100% 활용하는 최적화 대신 공통 분모를 취하는 범용 인터페이스를 유지해야 한다.

### ADR-002: 파일 기반 핸드오프 (File-based Handoff)
**결정**: 세션 간 상태 공유를 위해 별도의 데이터베이스 대신 로컬 JSON 파일(`-output.json`)을 사용한다.
**이유**: 별도의 인프라 구축 없이 Git 저장소만으로 작업 상태를 동기화하고, 누구나 쉽게 상태를 조회할 수 있게 하기 위함이다.
**트레이드오프**: 파일 충돌(Merge Conflict)의 위험이 있으나, 한 번에 하나의 스텝만 진행하는 하네스 규칙으로 이를 제어한다.

### ADR-003: 계약 우선 모듈 경계 (Contract-first Module Boundaries)
**결정**: 후속 step은 이전 step의 구현 전체가 아니라 `module-map.json`, phase baseline, public contract를 우선 입력으로 사용한다. 이전 구현 수정이 필요하면 현재 step에 섞지 않고 `blocking-fix`, `contract-change`, `module-fix`, `backlog-fix` step으로 승격한다.
**이유**: 매 step마다 이전 구현과 긴 handoff를 다시 읽는 토큰 낭비를 줄이면서도, contract test와 integration step을 통해 결과물 품질을 유지하기 위함이다.
**트레이드오프**: Step 0에서 모듈 경계와 contract를 더 신중하게 설계해야 하며, contract가 틀린 경우 별도 fix/change step이 추가된다.
