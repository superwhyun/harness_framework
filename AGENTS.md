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
- 후속 step은 이전 구현 전체가 아니라 `baseline`, `module-map`, public contract를 우선 읽는다.
- 품질이나 AC 때문에 이전 구현 확인이 필요하면 영향 모듈만 targeted read 한다.

## 문서 우선순위

작업 전에는 아래 순서로 읽는다.

1. `AGENTS.md`
2. `docs/HARNESS.md`
3. `docs/ARCHITECTURE.md`
4. `docs/ADR.md`
5. `phases/project-manifest.json` (있으면) — 전체 프로젝트 누적 현황
6. 현재 phase의 `phases/{task}/index.json`
7. 현재 phase의 `phases/{task}/module-map.json` (있으면)
8. 현재 step의 `phases/{task}/stepN.md`

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

- Step 0은 가능하면 `module-map`과 public contract 초안을 먼저 만든다.
- 한 step은 한 레이어 또는 한 모듈만 다룬다.
- 각 step은 `owned_paths`, `read_contracts`, `forbidden_paths`를 명시한다.
- 후속 step은 의존 모듈의 구현 내부가 아니라 public contract만 기본 입력으로 삼는다.
- 각 step은 독립 세션에서도 이해 가능해야 한다.
- step 안에는 읽을 파일, 구현 범위, 검증 명령, 금지사항이 있어야 한다.
- AC는 실제 실행 가능한 명령으로 쓴다.
- contract가 틀려 현재 step을 완료할 수 없으면 현재 step을 `blocked`로 기록하고 `blocking-fix` 또는 `contract-change` step을 append한다. append된 blocking step은 즉시 우선 수행한다.
- 현재 step을 막지 않는 개선사항은 현재 step을 완료한 뒤 phase 마지막에 `backlog-fix` step으로 append한다.
- 이미 존재하는 step 번호를 재정렬하거나 renumbering 하지 않는다. 새 step은 항상 append한다.
- 새 phase를 만들 때는 `scripts/scaffold_phase.py`를 사용한다. 대상 프로젝트가 `.harness/current_project`에 설정되어 있으면 `--root` 없이도 동작하고, 없으면 `--root projects/{project-name}`을 명시한다.
- phase 파일을 생성하거나 크게 수정한 뒤에는 `scripts/validate_phase.py`로 형식을 검증한다.

### 3. 실행

이미 `phases/{task}/index.json` 이 있으면 첫 `pending` step부터 이어서 진행한다.

- `completed`면 다음 step으로 간다.
- `blocked`면 이유를 기록한다. 단, 해당 blocked step을 해소하는 pending `blocking-fix` step이 있으면 그 step을 먼저 수행한다.
- `error`면 원인과 다음 액션을 남긴다.
- 한 step은 최대 3회까지만 재시도한다.
- `blocking-fix` 완료 후에는 `unblocks` 대상 step을 다시 `pending`으로 돌려 원래 작업을 재개한다.

**CRITICAL (Phase 마감 규칙):**
- 특정 Phase의 마지막 step이 `completed`가 되면, 즉시 상위 `phases/index.json`의 해당 Phase 상태를 `completed`로 업데이트해야 한다.
- Phase 마감 시 다음 phase가 전체 소스코드를 재탐색하지 않도록 `phases/baselines/{phase-dir}.json`에 모듈, public surface, shared contracts, routes, integration points를 요약해야 한다. 배치 실행기는 최소 baseline skeleton을 자동 생성한다.
- Phase 마감 시 배치 실행기는 `phases/project-manifest.json`에 해당 phase의 모듈, 라우트, 공유 계약, 통합 지점을 자동으로 누적한다. 새 phase의 에이전트는 이 파일을 읽어 전체 프로젝트 현황을 파악한다.
- Phase 마감 시 반드시 `git tag {project}-phase{N}-done`을 생성한다.

### 5. 세션 시작 및 탐색 (상태 정합성 체크)

- 새로운 세션을 시작할 때, 에이전트는 반드시 `phases/index.json`과 각 Phase별 `index.json`의 상태가 일치하는지 확인해야 한다.
- 만약 실제 작업 내용과 기록된 상태가 다를 경우, 즉시 상태를 동기화한 뒤 사용자에게 보고한다.

### 6. git 커밋

커밋은 **step 단위**로 한다. phase 단위로 묶지 않는다.

커밋 시점: AC 통과 직후.

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

### `phases/{task}/module-map.json`

- 현재 phase의 모듈 경계와 step 소유권을 관리한다.
- 각 모듈은 `owner_steps`, `owned_paths`, `contracts`, `dependencies`를 가진다.
- 후속 step은 이 파일을 기준으로 읽기/수정 범위를 제한한다.

### `phases/baselines/{phase-dir}.json`

- 완료된 phase의 압축된 결과 상태다.
- 다음 phase의 step0는 이전 phase의 구현 전체가 아니라 이 baseline과 public contract를 먼저 읽는다.

## 금지사항

- 여러 step을 한 세션에서 한꺼번에 밀어붙이지 마라.
- 현재 step 범위를 벗어난 기능을 추가하지 마라.
- 이전 step의 구현 내부를 기본 입력으로 삼아 재탐색하지 마라.
- `owned_paths` 밖의 구현 파일을 현재 step에 섞어 수정하지 마라.
- 기존 step을 중간에 끼워 넣기 위해 step 번호를 재정렬하지 마라.
- "대화 맥락이 있으니 다음 AI가 알아서 이해할 것"이라고 가정하지 마라.

## CRITICAL: git init 및 .gitignore 규칙

`git init`은 프로젝트 최초 scaffold 시 **딱 한 번만** 실행한다.

- `.git` 디렉터리가 이미 존재하면 `git init`을 절대 재실행하지 마라.
- 매 step마다 `git init`을 실행하는 것은 잘못된 동작이다.
- 커밋 전 반드시 `git status`로 repo 존재 여부를 먼저 확인한다.
- 이미 초기화된 repo에 `git init`을 재실행하면 설정이 손상될 수 있다.

**`.gitignore`는 `git init` 직후, 첫 `git add` 전에 반드시 작성한다.**

scaffold step에서 반드시 포함해야 할 항목:
```
# 의존성
node_modules/
.venv/
__pycache__/
*.pyc

# 빌드 산출물
dist/
build/
*.tsbuildinfo

# 환경 변수
.env
.env.local
.env.*.local

# OS / 에디터
.DS_Store
Thumbs.db
.vscode/
.idea/

# 배포 도구
.vercel

# 테스트 커버리지
coverage/
```

기술 스택에 맞게 추가하되, `.gitignore` 없이 `git add .`를 절대 실행하지 마라.

## CRITICAL: phases/ 디렉터리 보호

**`phases/` 디렉터리와 그 하위 파일은 절대 삭제하거나 덮어쓰지 마라.**

이 디렉터리는 프로젝트 구현 계획과 진행 상태를 담는 유일한 진실 공급원(SSOT)이다.
세션이 바뀌어도 이 파일들이 있어야 다음 AI가 작업을 이어받을 수 있다.

금지 행동:
- `rm -rf projects/{project-name}` 또는 프로젝트 디렉터리 삭제
- `phases/` 디렉터리 삭제 또는 재생성
- `phases/index.json`, `phases/{task}/index.json` 초기화
- `scaffold_phase.py`를 `--force` 없이 기존 phase에 재실행 (stepN.md 덮어쓰기)

새 세션 시작 시 **반드시** 아래 순서로 상태를 먼저 확인한다:
1. `phases/index.json` 읽기
2. `phases/project-manifest.json` 읽기 (있으면) — 전체 프로젝트 누적 현황
3. 첫 번째 `pending` phase의 `module-map.json` 읽기 (있으면)
4. 첫 번째 `pending` step의 `stepN.md` 읽기
5. 그 다음에 작업 시작

프로젝트 디렉터리에 `package.json`이 없거나 소스 코드가 없어도,
`phases/`가 존재하면 **신규 프로젝트가 아니라 진행 중인 프로젝트**다.
scaffold를 다시 실행하지 마라.

## 프로젝트 명령

- Claude Code: `/harness`, `/review`
- Gemini CLI: `/harness`, `/review`
- Kimi Code CLI: `/skill:harness`, `/skill:review`
- Codex: 별도 프로젝트 slash command는 전제하지 않는다. 대신 이 파일과 `docs/HARNESS.md`를 기준으로 사용자가 바로 작업을 요청하면 그 흐름을 따른다.
