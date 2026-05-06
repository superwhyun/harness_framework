# Harness Framework

이 파일은 이 저장소의 canonical 프로젝트 지침이다.
Codex에서는 이 파일을 기본 프로젝트 규칙으로 사용한다.
Claude Code, Gemini CLI, Kimi Code CLI에서도 이 파일 내용을 기준으로 작업해야 한다.

## 목적

이 저장소는 특정 벤더 전용 프롬프트 묶음이 아니라, 여러 코딩 에이전트가 공유할 수 있는 step 기반 하네스 워크플로우를 담는다.

핵심 목표는 아래다.

- 작업을 `phases/{task}/stepN.md` 단위로 쪼갠다.
- 한 세션이 끝나도 다음 세션에서 다른 AI 툴이 이어서 작업할 수 있게 한다.
- 진행 상태와 다음 액션을 구조적으로 남긴다.
- 자동 루프는 보수적으로 유지한다.

## 기본 원칙

- 한 번에 하나의 step만 진행한다.
- 완료 기준은 "사용자 만족"이 아니라 step에 적힌 Acceptance Criteria 통과 여부다.
- step 실행 중 무한 개선 루프를 돌리지 않는다.
- 한 step은 최대 3회까지만 재시도한다.
- 세션이 끝날 때는 다음 세션이 바로 이어받을 수 있게 handoff를 남긴다.

## 문서 우선순위

작업 전에는 아래 순서로 읽는다.

1. `AGENTS.md`
2. `docs/PRD.md`
3. `docs/ARCHITECTURE.md`
4. `docs/ADR.md`
5. `docs/UI_GUIDE.md` (UI 작업인 경우)
6. 현재 phase의 `phases/{task}/index.json`
7. 현재 step의 `phases/{task}/stepN.md`
8. 직전 step의 `phases/{task}/stepN-output.json` (있으면)

## 인터랙티브 사용 방식

이 저장소의 기본 사용 방식은 "리포를 툴에서 열고, 툴이 프로젝트 문서를 자동 로드한 상태에서 작업"이다.

- Codex: `AGENTS.md`를 기준 규칙으로 사용한다.
- Claude Code: `CLAUDE.md`와 `.claude/commands/`를 진입점으로 쓰되, canonical 내용은 `AGENTS.md`와 `docs/HARNESS.md`다.
- Gemini CLI: `GEMINI.md` 또는 `.gemini/settings.json`으로 `AGENTS.md`를 컨텍스트 파일로 읽고, `.gemini/commands/`를 프로젝트 명령으로 사용한다.
- Kimi Code CLI: `AGENTS.md`를 기본 프로젝트 규칙으로 읽고, `.kimi/skills/`의 project-level skills를 진입점으로 사용한다.

`scripts/execute.py`는 배치형 실행기일 뿐, 인터랙티브 사용에서 매번 직접 실행해야 하는 필수 진입점이 아니다.

## Harness 워크플로우

### 0. 대상 프로젝트 결정

하네스 프레임워크에서 실행할 때는 먼저 대상 프로젝트를 정한다.

1. 사용자가 명시한 프로젝트 경로를 우선 사용한다.
2. 없으면 `.harness/current_project` 값을 읽는다.
3. 둘 다 없거나 비어 있으면 사용자에게 대상 프로젝트 경로를 물어본다.

대상 프로젝트는 반드시 `projects/{project-name}/` 아래에 생성한다.
프레임워크 저장소의 `.gitignore`는 `projects/`를 추적하지 않는다.
`phases/`는 항상 `projects/{project-name}/phases/` 경로에 위치해야 한다. 프레임워크 루트나 다른 경로에 생성하지 마라.

### 1. 탐색

사용자 요청을 처리하기 전에 `docs/`와 관련 코드, 대상 프로젝트의 `phases/` 상태를 확인한다.

### 2. 계획

복잡한 작업이면 step 설계를 먼저 만든다.

설계 원칙:

- 한 step은 한 레이어 또는 한 모듈만 다룬다.
- 각 step은 독립 세션에서도 이해 가능해야 한다.
- step 안에는 읽을 파일, 구현 범위, 검증 명령, 금지사항이 있어야 한다.
- AC는 실제 실행 가능한 명령으로 쓴다.
- 새 phase를 만들 때는 `scripts/scaffold_phase.py`를 사용한다. 대상 프로젝트가 `.harness/current_project`에 설정되어 있으면 `--root` 없이도 동작하고, 없으면 `--root projects/{project-name}`을 명시한다.
- phase 파일을 생성하거나 크게 수정한 뒤에는 `scripts/validate_phase.py`로 형식을 검증한다.

### 3. 실행

이미 `phases/{task}/index.json` 이 있으면 첫 `pending` step부터 이어서 진행한다.

- `completed`면 다음 step으로 간다.
- `blocked`면 즉시 중단하고 이유를 기록한다.
- `error`면 원인과 다음 액션을 남긴다.
- 한 step은 최대 3회까지만 재시도한다.

### 4. handoff 기록

세션 종료 전에는 현재 step의 output JSON에 가능한 한 아래를 남긴다.

- `summary`, `completed_work`, `files_changed`, `decisions`, `verification`, `known_issues`, `next_actions`, `blockers`, `resume_hint`

**CRITICAL (Phase 마감 규칙):**
- 특정 Phase의 마지막 step이 `completed`가 되면, 즉시 상위 `phases/index.json`의 해당 Phase 상태를 `completed`로 업데이트해야 한다.
- Phase 마감 시 반드시 `git tag {project}-phase{N}-done`을 생성한다.

### 5. 세션 시작 및 탐색 (상태 정합성 체크)

- 새로운 세션을 시작할 때, 에이전트는 반드시 `phases/index.json`과 각 Phase별 `index.json`의 상태가 일치하는지 확인해야 한다.
- 만약 실제 작업 내용과 기록된 상태가 다를 경우, 즉시 상태를 동기화한 뒤 사용자에게 보고한다.

### 6. git 커밋

커밋은 **step 단위**로 한다. phase 단위로 묶지 않는다.

커밋 시점: AC 통과 + `stepN-output.json` 작성 직후.

커밋 메시지 형식:
```
feat({project}/step{N}): {step-name} — {한 줄 요약}
```

phase 완료 시 태그:
```bash
git tag {project}-phase{N}-done
```

자세한 내용은 `docs/HARNESS.md`의 "F. Git 커밋" 섹션을 참조한다.

## 상태 파일 규칙

### `phases/index.json`

- 여러 task의 top-level 상태를 관리한다.

### `phases/{task}/index.json`

- step 목록과 상태를 관리한다.
- `status`는 `pending`, `completed`, `error`, `blocked` 중 하나다.

### `phases/{task}/stepN.md`

- 해당 step의 실행 지시서다.

### `phases/{task}/stepN-output.json`

- 세션 handoff 기록이다.
- 다음 세션은 이 파일을 읽고 이어서 작업해야 한다.

## 금지사항

- 여러 step을 한 세션에서 한꺼번에 밀어붙이지 마라.
- 현재 step 범위를 벗어난 기능을 추가하지 마라.
- handoff 없이 세션을 끝내지 마라.
- "대화 맥락이 있으니 다음 AI가 알아서 이해할 것"이라고 가정하지 마라.

## 프로젝트 명령

- Claude Code: `/harness`, `/review`
- Gemini CLI: `/harness`, `/review`
- Kimi Code CLI: `/skill:harness`, `/skill:review`
- Codex: 별도 프로젝트 slash command는 전제하지 않는다. 대신 이 파일과 `docs/HARNESS.md`를 기준으로 사용자가 바로 작업을 요청하면 그 흐름을 따른다.
