# Harness Workflow

이 문서는 이 저장소의 범용 하네스 워크플로우 원문이다.
Claude Code, Gemini CLI, Kimi Code CLI, Codex 모두 이 문서를 기준으로 작업해야 한다.

## 목표

- 작업을 step 단위로 분해한다.
- step 상태를 파일로 관리한다.
- 세션이 끝나도 다른 AI 툴이 이어받을 수 있게 handoff를 남긴다.
- 자동 반복은 최대 3회 재시도로 제한한다.

## 실행 순서

### A. 탐색

먼저 아래를 읽고 현재 상태를 파악한다.

- `AGENTS.md`
- `docs/PRD.md`
- `docs/ARCHITECTURE.md`
- `docs/ADR.md`
- `docs/UI_GUIDE.md` (필요한 경우)
- 현재 `phases/` 관련 파일

### B. 논의

구현 전에 결정이 더 필요한 사항이 있으면 사용자와 먼저 정리한다.

### C. Step 설계

사용자가 계획을 원하거나 작업이 크다면 아래 원칙으로 step을 만든다.

1. Scope를 최소화한다.
2. 각 step은 독립 세션에서도 이해 가능해야 한다.
3. 읽어야 할 문서와 파일을 명시한다.
4. AC는 실행 가능한 명령으로 적는다.
5. 금지사항은 추상적으로 쓰지 말고 구체적으로 쓴다.

### D. 실행

이미 `phases/{task}/index.json` 이 있으면 첫 `pending` step부터 이어서 작업한다.

- `completed`면 다음 step으로 이동
- `blocked`면 즉시 중단
- `error`면 원인과 재개 힌트를 남기고 중단
- step당 최대 3회 재시도

### E. handoff

세션 종료 전에는 `stepN-output.json`에 최소 아래를 남긴다.

- `summary`
- `files_changed`
- `verification`
- `known_issues`
- `next_actions`
- `resume_hint`

가능하면 아래도 함께 남긴다.

- `completed_work`
- `decisions`
- `blockers`

## 상태 파일 포맷

### `phases/index.json`

```json
{
  "phases": [
    {
      "dir": "0-mvp",
      "status": "pending"
    }
  ]
}
```

### `phases/{task}/index.json`

```json
{
  "project": "ExampleProject",
  "phase": "mvp",
  "steps": [
    { "step": 0, "name": "project-setup", "status": "pending" },
    { "step": 1, "name": "core-types", "status": "pending" }
  ]
}
```

### `phases/{task}/stepN.md`

step 실행 지시서에는 아래가 있어야 한다.

- 읽어야 할 파일
- 작업 범위
- Acceptance Criteria
- 검증 절차
- 금지사항

## 배치 실행기

`scripts/execute.py` 는 선택적 배치 실행기다.
필요할 때만 사용한다.

```bash
python3 scripts/execute.py 0-mvp
python3 scripts/execute.py 0-mvp --backend codex
python3 scripts/execute.py 0-mvp --backend gemini
python3 scripts/execute.py 0-mvp --backend kimi
python3 scripts/execute.py 0-mvp --backend claude
```

기본 사용 방식은 위 스크립트를 수동으로 실행하는 것이 아니라, 각 AI 코딩툴이 이 저장소의 문서를 읽고 인터랙티브하게 작업하는 것이다.
