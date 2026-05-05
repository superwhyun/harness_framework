# Harness Workflow

이 문서는 이 저장소의 범용 하네스 워크플로우 원문이다.
Claude Code, Gemini CLI, Kimi Code CLI, Codex 모두 이 문서를 기준으로 작업해야 한다.

## 목표
- 작업을 step 단위로 분해한다.
- step 상태를 파일로 관리한다.
- 세션이 끝나도 다른 AI 툴이 이어받을 수 있게 handoff를 남긴다.
- 자동 반복은 최대 3회 재시도로 제한한다.

## 실행 순서

### 대상 프로젝트 결정

하네스 프레임워크에서 작업할 때는 먼저 대상 프로젝트를 정한다.

1. 사용자가 명시한 프로젝트 경로를 우선 사용한다.
2. 없으면 `.harness/current_project` 값을 읽는다.
3. 둘 다 없거나 비어 있으면 사용자에게 대상 프로젝트 경로를 물어본다.

대상 프로젝트는 반드시 `projects/{project-name}/` 아래에 생성한다.
`phases/`는 항상 `projects/{project-name}/phases/` 경로에 위치해야 한다. 프레임워크 루트나 다른 경로에 생성하지 마라.

### A. 탐색 (Discovery)
먼저 아래를 읽고 현재 상태를 파악한다.
1. `AGENTS.md` (공통 규칙)
2. `docs/PRD.md`, `docs/ARCHITECTURE.md`, `docs/ADR.md`
3. 대상 프로젝트의 `phases/index.json` 및 `phases/{task}/index.json`

### B. 논의 (Discussion)
구현 전에 결정이 더 필요한 사항이 있으면 사용자와 먼저 정리한다.

새 기능 요청이 들어왔을 때 아래 조건 중 하나라도 해당하면 **반드시 새 phase를 설계하고 사용자 승인을 받은 뒤 실행한다**:
- 현재 모든 phase가 `completed` 상태인 경우
- 요청이 기존 phase 범위를 벗어난 새 기능인 경우

사용자가 명시적으로 "phase 설계"를 언급하지 않아도 위 조건이 충족되면 AI가 먼저 phase 설계안을 제시한다.

### C. Step 설계 (Planning)
필요 시 `scripts/scaffold_phase.py`를 사용하여 페이즈를 설계한다.

```bash
# .harness/current_project가 설정된 경우
python3 scripts/scaffold_phase.py {phase-dir} --project {name} --steps step1 step2 ...

# 설정이 없는 경우 --root 명시
python3 scripts/scaffold_phase.py {phase-dir} --project {name} --steps step1 step2 ... --root projects/{project-name}
```

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

### F. Git 커밋 (Commit)

커밋은 **step 단위**로 한다. phase 단위로 묶지 않는다.

**커밋 위치**: `projects/{project-name}/` 의 자체 git repo 안에서 실행한다.
harness framework 루트에서 실행하면 `projects/`가 gitignore 대상이라 동작하지 않는다.

**커밋 시점**: AC를 통과하고 `stepN-output.json` handoff를 작성한 직후.

**커밋 메시지 형식**:
```
feat({project}/step{N}): {step-name} — {한 줄 요약}
```

예시:
```
feat(debate/step0): project-setup — package skeleton
feat(debate/step2): llm-clients — 5 backends async
feat(debate/step8): web-api — FastAPI routes + output.py
```

**phase 완료 시**: 마지막 step 커밋 후 태그를 단다.
```bash
git tag {project}-phase{N}-done
# 예: git tag debate-phase0-done
```

**이유**:
- step별 AC 통과 = 자연스러운 커밋 경계
- 특정 step 실패 시 해당 step만 revert 가능
- 다른 AI 툴이 이어받을 때 git log에서 진행 상태 파악 가능

## 상태 파일 포맷
- `phases/index.json`: 페이즈 목록 및 최상위 상태.
- `phases/{task}/index.json`: 스텝 목록 및 상태.
- `phases/{task}/stepN.md`: 실행 지시서.
- `phases/{task}/stepN-output.json`: 세션 핸드오프 기록.
