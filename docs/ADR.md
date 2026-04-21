# Architecture Decision Records (ADR): FG-EAI

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

### ADR-003: ITU-T F.748.66과의 정렬 (ITU-T Alignment)
**결정**: 모든 Embodied AI 관련 용어와 요구사항은 ITU-T F.748.66(Requirements and framework for embodied AI systems)의 정의를 최우선으로 따른다.
**이유**: 국제 표준과의 정렬을 통해 향후 권고안(Recommendation) 채택 가능성을 높이기 위함이다.
**트레이드오프**: 최신 학계 용어와 표준 용어 간의 차이가 발생할 수 있으며, 이 경우 표준 용어를 공식적으로 채택한다.
