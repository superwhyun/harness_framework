# Harness Framework

Step 기반으로 작업을 분해하고, 세션이 끝나도 다른 AI 코딩툴이 이어서 작업할 수 있게 만드는 범용 하네스 템플릿이다.

이 저장소의 목표는 아래 3가지다.

- 작업을 `phases/{task}/stepN.md` 단위로 쪼갠다.
- 진행 상태를 `index.json` 과 `stepN-output.json` 에 남긴다.
- Claude Code, Codex, Gemini CLI, Kimi Code CLI 중 어떤 툴을 쓰더라도 같은 상태 파일을 읽고 이어서 작업할 수 있게 한다.

## 핵심 개념

이 저장소는 "한 세션에서 끝까지 다 해내는 자율 루프"가 아니다.

- 한 번에 하나의 step만 다룬다.
- step 완료 기준은 사용자의 막연한 만족이 아니라 step의 Acceptance Criteria 통과 여부다.
- 한 step은 최대 3회까지만 재시도한다.
- 세션이 끝나면 다음 세션을 위해 handoff를 남긴다.

즉, 핵심은 무한 자동화가 아니라 "구조화된 작업 기록과 안전한 재개"다.

## 문서 우선순위

어떤 툴을 쓰든 먼저 아래 순서로 읽는다.

1. `AGENTS.md`
2. `docs/HARNESS.md`
3. `docs/PRD.md`
4. `docs/ARCHITECTURE.md`
5. `docs/ADR.md`
6. `docs/UI_GUIDE.md` (UI 작업인 경우)
7. 현재 `phases/` 관련 파일

이 중 canonical 프로젝트 규칙은 `AGENTS.md` 이다.

## 어떤 식으로 쓰는가

이 저장소의 기본 사용 방식은 `python` 스크립트를 매번 직접 실행하는 것이 아니다.

정상적인 사용 방식은 아래다.

- `harness_framework` 리포를 AI 코딩툴에서 연다.
- 실제 산출 프로젝트는 `projects/{project}` 아래의 독립 Git 저장소로 둔다.
- 툴이 프로젝트 규칙 파일을 자동 로드한다.
- 대상 프로젝트의 `phases/` 상태를 읽고 첫 `pending` step부터 진행한다.
- 세션 종료 시 `stepN-output.json` 에 handoff를 남긴다.
- 다음 세션에서 다른 툴이 그 handoff를 읽고 이어서 작업한다.

즉, `scripts/execute.py` 는 선택적 배치 실행기이고, 메인 진입점은 각 툴의 프로젝트 규칙/명령이다.

대상 프로젝트 결정 순서는 아래다.

1. 사용자가 명시한 프로젝트 경로
2. `.harness/current_project` 에 저장된 active project
3. 둘 다 없거나 비어 있으면 사용자에게 질문

active project는 아래처럼 설정한다.

```bash
python3 scripts/use_project.py projects/harness_project_alpha
```

## 툴별 사용법

### Claude Code

이 저장소는 Claude Code용 프로젝트 명령을 포함한다.

- 프로젝트 규칙 진입점: `CLAUDE.md`
- 프로젝트 명령: `.claude/commands/harness.md`, `.claude/commands/review.md`

리포를 열고 아래처럼 쓰면 된다.

```text
/harness
/review
```

의미:

- `/harness`: active project의 현재 phase를 이어서 진행
- `/review`: active project의 현재 변경사항 리뷰

### Gemini CLI

이 저장소는 Gemini CLI용 프로젝트 컨텍스트와 프로젝트 명령을 포함한다.

- 컨텍스트 파일 설정: `.gemini/settings.json`
- 프로젝트 명령: `.gemini/commands/harness.toml`, `.gemini/commands/review.toml`

리포를 열고 아래처럼 쓰면 된다.

```text
/harness
/review
```

의미는 Claude와 같다.

### Antigravity (IDE 통합 에이전트)

Antigravity는 IDE나 에디터 내부에 통합된 AI 어시스턴트로, 터미널 기반의 단독 도구인 **Gemini CLI와는 동작 방식이 다릅니다.**

> **Note: Gemini CLI와의 차이점**
> Gemini CLI는 `.gemini/commands/*.toml`을 파싱하여 `/harness` 같은 슬래시 커맨드를 시스템 자체에 등록하지만, Antigravity는 전역 설정(`~/.gemini/antigravity/` 하위)을 우선적으로 로드하므로 리포지토리 로컬의 커스텀 `.toml` 설정이 자동완성 UI 커맨드로 즉시 노출되지는 않습니다.

하지만 시스템 UI에만 노출되지 않을 뿐, 이미 `AGENTS.md`와 `GEMINI.md` 규칙을 이해하고 있으므로 채팅창에 아래와 같이 입력하면 완벽하게 동일한 워크플로우를 수행할 수 있습니다.

```text
/harness
/review
```
또는 자연어로:
```text
harness 워크플로우 진행해줘
리뷰 워크플로우를 따라 현재 코드 리뷰해줘
```

### Kimi Code CLI

Kimi는 project-level skills를 자동 발견하는 방식이 가장 자연스럽다.
이 저장소는 `.kimi/skills/` 아래에 harness/review skill을 포함한다.

- 프로젝트 규칙: `AGENTS.md`
- project-level skills: `.kimi/skills/harness/`, `.kimi/skills/review/`

리포를 열고 아래처럼 쓰면 된다.

```text
/skill:harness
/skill:review
```

의미:

- `/skill:harness`: `AGENTS.md` 와 `docs/HARNESS.md` 를 기준으로 현재 phase를 이어서 진행
- `/skill:review`: `docs/REVIEW.md` 기준으로 현재 변경사항 리뷰

### Codex

Codex는 이 저장소에서 `AGENTS.md` 를 canonical 프로젝트 규칙으로 사용하도록 정리되어 있다.

Codex에서는 프로젝트 slash command를 전제하지 않는다.
그 대신 자연어로 바로 요청하면 된다.

예:

```text
현재 phases 상태를 읽고 첫 pending step부터 진행해
docs/HARNESS.md 기준으로 harness workflow를 따라
현재 변경사항을 docs/REVIEW.md 기준으로 리뷰해
```

framework 리포에서 작업할 때는 대상 프로젝트를 함께 지정하거나 active project를 먼저 설정한다.

```text
projects/harness_project_alpha를 대상 프로젝트로 보고 첫 pending step부터 진행해
```

## 빠른 시작

### 1. 새 task 시작

새 작업을 만들 때는 아래 파일들을 만든다.

- `phases/index.json`
- `phases/{task}/index.json`
- `phases/{task}/step0.md`
- 필요하면 `step1.md`, `step2.md` ...

예시:

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

```json
{
  "project": "ExampleProject",
  "phase": "mvp",
  "steps": [
    { "step": 0, "name": "project-setup", "status": "pending" },
    { "step": 1, "name": "core-types", "status": "pending" },
    { "step": 2, "name": "api-layer", "status": "pending" }
  ]
}
```

### 2. step 작성

각 `stepN.md` 에는 최소 아래가 있어야 한다.

- 읽어야 할 파일
- 작업 범위
- Acceptance Criteria
- 검증 절차
- 금지사항

권장 원칙:

- 한 step은 한 레이어 또는 한 모듈만 다룬다.
- 독립 세션에서도 이해 가능하게 쓴다.
- "이전 대화에서 말했듯" 같은 표현은 쓰지 않는다.
- AC는 실제 실행 가능한 명령으로 쓴다.

자동 생성을 표준화하고 싶으면 아래를 사용할 수 있다.

```bash
python3 scripts/use_project.py projects/harness_project_alpha
python3 scripts/scaffold_phase.py 0-mvp --project ExampleProject --phase-name mvp --steps project-setup core-types api-layer
python3 scripts/validate_phase.py 0-mvp
```

### 3. 진행

AI 툴은 현재 `phases/{task}/index.json` 에서 첫 `pending` step을 찾고, 해당 step을 수행한다.

상태는 아래 중 하나다.

- `pending`
- `completed`
- `error`
- `blocked`

### 4. 세션 종료

세션이 끝날 때는 `phases/{task}/stepN-output.json` 에 handoff를 남긴다.

최소 권장 필드:

- `summary`
- `files_changed`
- `verification`
- `known_issues`
- `next_actions`
- `resume_hint`

가능하면 함께 남길 필드:

- `completed_work`
- `decisions`
- `blockers`

## 세션을 툴 간에 넘기는 방식

이 저장소는 "작업 도중 실시간 전환"을 목표로 하지 않는다.
지원하는 것은 "세션 종료 후 다른 툴로 재개"다.

예:

1. Claude Code에서 step 0 완료
2. `step0-output.json` 생성
3. 다음 날 Gemini CLI에서 리포를 열고 `/harness`
4. Gemini가 `index.json` 과 `step0-output.json` 을 읽고 step 1부터 이어서 진행

다음 세션은 이전 대화 로그가 아니라 상태 파일과 handoff 파일을 기준으로 이어받아야 한다.

## 리뷰 방식

리뷰 기준은 `docs/REVIEW.md` 이다.

리뷰 시 확인할 것:

- 아키텍처 구조 준수
- ADR 기술 선택 준수
- 테스트 존재 여부
- handoff 파일과 실제 코드 상태의 일치 여부
- 빌드/테스트 통과 여부

## 선택적 배치 실행기

`scripts/execute.py` 는 선택적 배치 실행기다.
CI, 자동 실험, 또는 로컬 일괄 실행이 필요할 때만 쓴다.

예:

```bash
python3 scripts/execute.py 0-mvp
python3 scripts/execute.py --root projects/harness_project_alpha 0-mvp
python3 scripts/execute.py 0-mvp --backend claude
python3 scripts/execute.py 0-mvp --backend codex
python3 scripts/execute.py 0-mvp --backend gemini
python3 scripts/execute.py 0-mvp --backend kimi
python3 scripts/execute.py 0-mvp --backend codex --push
```

기본 backend 설정은 `harness.json` 에 있다.

## backend 설정

`harness.json` 은 배치 실행기용 backend 설정 파일이다.

현재 기본값:

- `claude`
- `codex`
- `gemini`
- `kimi`

예:

```json
{
  "default_backend": "claude"
}
```

원하면 각 backend 명령을 프로젝트 상황에 맞게 바꿀 수 있다.

### 보안 설정 (dangerous_mode)

기본적으로 하네스는 보수적인 모드로 실행된다. 각 백엔드의 dangerous 플래그(`--dangerously-skip-permissions`, `--approval-mode yolo` 등)는 **기본값에서 제외**되어 있다.

CI나 배치 자동화에서 이러한 플래그가 필요한 경우, `harness.json`에 아래를 추가한다.

```json
{
  "dangerous_mode": true
}
```

`dangerous_mode: true`일 때만 기존의 aggressive 플래그가 복원된다. 이 설정 없이는 각 백엔드가 기본 권한 모드로 실행된다.

## backend smoke check

mock 테스트 외에 실제 설치된 CLI의 help surface를 검증하려면 아래를 실행한다.

```bash
python3 scripts/smoke_backends.py
```

이 스크립트는 아래를 실제로 확인한다.

- `claude --help`
- `codex exec --help`
- `gemini --help`
- `kimi --help`
- `ollama --help`
- `lms --help` (LM Studio CLI)

즉, 문서상 지원이 아니라 현재 머신의 실제 CLI가 우리가 기대하는 플래그 surface를 유지하는지 확인하는 용도다.

## 디렉터리 구조

```text
.
├── AGENTS.md
├── CLAUDE.md
├── GEMINI.md
├── docs/
│   ├── HARNESS.md
│   ├── REVIEW.md
│   ├── PRD.md
│   ├── ARCHITECTURE.md
│   ├── ADR.md
│   └── UI_GUIDE.md
├── .claude/
│   └── commands/
├── .gemini/
│   ├── settings.json
│   └── commands/
├── .kimi/
│   └── skills/
├── .harness/
│   └── current_project
├── projects/
│   └── {project}/
│       ├── .git
│       ├── phases/
│       │   └── {task}/
│       │       ├── index.json
│       │       ├── step0.md
│       │       └── step0-output.json
│       └── 실제 코드
├── harness.json
└── scripts/
    └── execute.py
```

## 권장 운영 방식

- 프로젝트 규칙은 `AGENTS.md` 에만 canonical 하게 유지한다.
- 툴별 파일은 supplement/shim 으로만 둔다.
- step은 작게 쪼갠다.
- handoff는 항상 남긴다.
- 다음 세션은 대화 맥락이 아니라 파일 상태를 기준으로 이어간다.

## 언제 `python`을 쓰는가

보통은 안 쓴다.

`scripts/execute.py` 를 직접 쓰는 경우는 아래 정도다.

- 로컬에서 배치 실행을 돌리고 싶을 때
- 특정 backend로 같은 phase를 일괄 실행해 보고 싶을 때
- CI/자동화에서 비대화식으로 실행하고 싶을 때

그 외의 일반 사용은 Claude Code, Codex, Gemini CLI 안에서 바로 작업하면 된다.
