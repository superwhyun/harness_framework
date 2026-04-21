# Harness Workflow

이 문서는 이 저장소의 범용 하네스 워크플로우 원문이다.
Claude Code, Gemini CLI, Kimi Code CLI, Codex 모두 이 문서를 기준으로 작업해야 한다.

## 목표
- 작업을 step 단위로 분해한다.
- step 상태를 파일로 관리한다.
- 세션이 끝나도 다른 AI 툴이 이어받을 수 있게 handoff를 남긴다.
- 자동 반복은 최대 3회 재시도로 제한한다.

## 실행 순서

### A. 탐색 (Discovery)
먼저 아래를 읽고 현재 상태를 파악한다.
1. `AGENTS.md` (공통 규칙)
2. `docs/PRD.md`, `docs/ARCHITECTURE.md`, `docs/ADR.md`
3. 현재 `phases/index.json` 및 `phases/{task}/index.json`

### B. 논의 (Discussion)
구현 전에 결정이 더 필요한 사항이 있으면 사용자와 먼저 정리한다.

### C. Step 설계 (Planning)
필요 시 `scripts/scaffold_phase.py`를 사용하여 페이즈를 설계한다.
1. Scope를 최소화한다 (한 번에 한 스텝만).
2. 각 step은 독립 세션에서도 이해 가능해야 한다.
3. AC는 실행 가능한 명령으로 적는다.

### D. 실행 (Execution)
`pending` 상태인 스텝부터 이어서 작업한다.
- `completed`면 다음 스텝으로 이동.
- `blocked`면 이유 기록 후 즉시 중단.
- `error`면 원인과 재개 힌트 남기고 중단.
- 스텝당 최대 3회 재시도.

### E. 핸드오프 (Handoff)
세션 종료 전에는 `stepN-output.json`에 최소 아래를 남긴다.
- `summary`, `files_changed`, `verification`, `known_issues`, `next_actions`, `resume_hint`

## 상태 파일 포맷
- `phases/index.json`: 페이즈 목록 및 최상위 상태.
- `phases/{task}/index.json`: 스텝 목록 및 상태.
- `phases/{task}/stepN.md`: 실행 지시서.
- `phases/{task}/stepN-output.json`: 세션 핸드오프 기록.
