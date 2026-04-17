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

- 리포를 AI 코딩툴에서 연다.
- 툴이 프로젝트 규칙 파일을 자동 로드한다.
- 현재 `phases/` 상태를 읽고 첫 `pending` step부터 진행한다.
- 세션 종료 시 `stepN-output.json` 에 handoff를 남긴다.
- 다음 세션에서 다른 툴이 그 handoff를 읽고 이어서 작업한다.

즉, `scripts/execute.py` 는 선택적 배치 실행기이고, 메인 진입점은 각 툴의 프로젝트 규칙/명령이다.

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

- `/harness`: `AGENTS.md` 와 `docs/HARNESS.md` 를 기준으로 현재 phase를 이어서 진행
- `/review`: `docs/REVIEW.md` 기준으로 현재 변경사항 리뷰

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
├── phases/
│   └── {task}/
│       ├── index.json
│       ├── step0.md
│       └── step0-output.json
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
