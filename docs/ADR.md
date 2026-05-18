# Architecture Decision Records (ADR)

## 철학
- **상태 기반 협업 (State-based Collaboration):** AI 에이전트 간의 소통은 대화 로그보다 구조화된 파일 상태를 우선한다.
- **최소 의존성 (Minimal Dependency):** 특정 벤더 도구에 종속되지 않는 범용 기술(Python, Markdown, JSON)을 사용하여 환경 이식성을 높인다.
- **결정의 가시성 (Decision Traceability):** 모든 작업의 판단 근거를 `ADR`과 커밋 메시지에 남겨, 나중에라도 추론이 가능하게 한다.

---

### ADR-001: 범용 하네스 전환 (Harness Generalization)
**결정**: 기존 Claude 전용 하네스 인프라를 Gemini, Codex, Kimi 등을 지원하는 범용 인프라로 전환한다.
**이유**: 단일 에이전트의 한계를 극복하고, 각 상황에 맞는 최적의 AI 모델을 선택하여 프로젝트를 완수하기 위함이다.
**트레이드오프**: 에이전트별 특성을 100% 활용하는 최적화 대신 공통 분모를 취하는 범용 인터페이스를 유지해야 한다.

### ADR-002: 계약 우선 세션 연속성 (Contract-first Session Continuity)
**결정**: 세션 간 상태 공유는 `stepN-output.json` handoff 대신 `module-map.json`, `phases/baselines/{phase-dir}.json`, public contract를 기본 입력으로 사용한다.
**이유**: handoff 파일 작성·읽기에 소모되는 토큰과 에너지를 줄이고, 이미 git과 baseline이 커버하지 않는 정보가 없음을 확인했기 때문이다.
**트레이드오프**: 세션이 step 중간에 중단된 경우 복구 수단이 git log와 index.json 상태뿐이므로, step이 원자 단위로 완결되는 하네스 규칙을 더 엄격히 지켜야 한다.

### ADR-003: 계약 우선 모듈 경계 (Contract-first Module Boundaries)
**결정**: 후속 step은 이전 step의 구현 전체가 아니라 `module-map.json`, phase baseline, public contract를 우선 입력으로 사용한다. 이전 구현 수정이 필요하면 현재 step에 섞지 않고 `blocking-fix`, `contract-change`, `module-fix`, `backlog-fix` step으로 승격한다.
**이유**: 매 step마다 이전 구현 전체를 다시 읽는 토큰 낭비를 줄이면서도, contract test와 integration step을 통해 결과물 품질을 유지하기 위함이다.
**트레이드오프**: Step 0에서 모듈 경계와 contract를 더 신중하게 설계해야 하며, contract가 틀린 경우 별도 fix/change step이 추가된다.
