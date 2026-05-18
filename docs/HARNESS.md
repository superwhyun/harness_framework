# Harness Workflow

이 문서는 이 저장소의 범용 하네스 워크플로우 원문이다.
Claude Code, Gemini CLI, Kimi Code CLI, Codex 모두 이 문서를 기준으로 작업해야 한다.

## 목표
- 작업을 step 단위로 분해한다.
- step 상태를 파일로 관리한다.
- 자동 반복은 최대 3회 재시도로 제한한다.
- 후속 step은 이전 구현 전체 대신 baseline, module-map, public contract를 우선 읽어 토큰 사용을 줄인다.
- 코드 품질을 위해 필요한 경우에는 영향 모듈만 targeted read 하고, 수정은 별도 fix/change step으로 분리한다.

## 실행 순서

### 대상 프로젝트 결정

하네스 프레임워크에서 작업할 때는 먼저 대상 프로젝트를 정한다.

1. 사용자가 명시한 프로젝트 경로를 우선 사용한다.
2. 없으면 `.harness/current_project` 값을 읽는다.
3. 둘 다 없거나 비어 있으면 사용자에게 대상 프로젝트 경로를 물어본다.

대상 프로젝트는 반드시 `projects/{project-name}/` 아래에 생성한다.
`phases/`는 항상 `projects/{project-name}/phases/` 경로에 위치해야 한다. 프레임워크 루트나 다른 경로에 생성하지 마라.

### A. 탐색 (Discovery)

**CRITICAL — 탐색 전 필수 확인:**
대상 프로젝트 디렉터리에 `phases/` 가 존재하면 **진행 중인 프로젝트**다.
`package.json`이나 소스 코드가 없어도 마찬가지다.
이 경우 scaffold를 재실행하거나 디렉터리를 삭제·초기화하지 마라.
반드시 `phases/index.json`을 읽고 첫 `pending` step부터 이어서 진행한다.

먼저 아래를 읽고 현재 상태를 파악한다.
1. `AGENTS.md` (공통 규칙)
2. `docs/ARCHITECTURE.md`, `docs/ADR.md`
3. 대상 프로젝트의 `phases/index.json` 및 `phases/{task}/index.json`
4. `phases/project-manifest.json` (있으면) — 전체 프로젝트 누적 현황
5. 현재 phase의 `phases/{task}/module-map.json` (있으면)
6. 현재 step의 `stepN.md`
7. 직전 step output은 복구가 필요할 때만 읽는다.

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
2. Step 0은 가능하면 `module-map.json`과 public contract 초안을 만든다.
3. 각 step은 독립 세션에서도 이해 가능해야 한다.
4. 각 step은 `owned_paths`, `read_contracts`, `forbidden_paths`를 명시한다.
5. 후속 step은 의존 모듈의 구현 내부가 아니라 public contract를 기본 입력으로 삼는다.
6. AC는 실행 가능한 명령으로 적는다.
7. 현재 step을 막는 외부 contract/모듈 문제가 발견되면 현재 step을 `blocked`로 기록하고 `blocking-fix` 또는 `contract-change` step을 append한다.
8. 현재 step을 막지 않는 개선사항은 phase 마지막에 `backlog-fix` step으로 append한다.
9. 기존 step 번호는 재정렬하지 않는다. 새 step은 항상 append한다.

### D. 실행 (Execution)
`pending` 상태인 스텝부터 이어서 작업한다.
- `completed`면 다음 스텝으로 이동.
- `blocked`면 이유를 기록한다. 단, pending `blocking-fix` step이 있으면 그 step을 먼저 수행한다.
- `error`면 원인과 재개 힌트 남기고 중단.
- 스텝당 최대 3회 재시도.
- `blocking-fix` step 완료 후에는 `unblocks` 대상 step을 다시 `pending`으로 풀고 원래 흐름으로 돌아간다.

### E. Phase 마감 (Baseline)

phase 종료 시에는 다음 phase가 전체 구현을 다시 읽지 않도록 `phases/baselines/{phase-dir}.json`에 아래를 남긴다. 배치 실행기는 최소 baseline skeleton을 자동 생성하며, 에이전트는 필요한 경우 내용을 더 풍부하게 보강한다.
- 완료 tag
- 모듈 목록과 public surface
- shared contracts
- routes 또는 외부 진입점
- integration points
- known issues

### F. Git 커밋 (Commit)

커밋은 **step 단위**로 한다. phase 단위로 묶지 않는다.

**커밋 위치**: `projects/{project-name}/` 의 자체 git repo 안에서 실행한다.
harness framework 루트에서 실행하면 `projects/`가 gitignore 대상이라 동작하지 않는다.

**`git init` 규칙**:
- `git init`은 프로젝트 최초 생성 시(scaffold step) **딱 한 번만** 실행한다.
- `.git` 디렉터리가 이미 존재하면 `git init`을 절대 재실행하지 마라.
- 커밋 전에는 반드시 `git status`로 repo 존재 여부를 확인한다.
- 이미 repo가 있는데 `git init`을 실행하면 기존 git 설정이 손상될 수 있다.

**`.gitignore` 규칙**:
- `git init` 직후, 첫 `git add` 실행 전에 `.gitignore`를 반드시 작성한다.
- `.gitignore` 없이 `git add .` 또는 `git add -A`를 실행하지 마라.
- 반드시 포함해야 할 항목: `node_modules/`, `dist/`, `build/`, `.env*`, `.DS_Store`, `*.tsbuildinfo`, `.vercel`, `coverage/`, `__pycache__/`, `.venv/`
- 기술 스택에 따라 추가 항목을 포함한다.

**커밋 시점**: AC를 통과한 직후.

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
- `phases/project-manifest.json`: 전체 프로젝트 누적 현황 (모듈, 라우트, 공유 계약, 통합 지점). Phase 완료 시 자동 업데이트.
- `phases/{task}/index.json`: 스텝 목록 및 상태.
- `phases/{task}/module-map.json`: 모듈 경계, 소유 step, owned paths, public contracts, dependencies.
- `phases/{task}/stepN.md`: 실행 지시서.
- `phases/baselines/{phase-dir}.json`: 완료 phase의 압축된 기준선.

## CRITICAL: phases/ 보호 규칙

`phases/` 디렉터리는 프로젝트의 구현 계획과 진행 상태를 담는 SSOT다.
어떤 상황에서도 아래 행동은 금지한다:

- 프로젝트 디렉터리(`projects/{project-name}/`) 삭제 또는 재생성
- `phases/` 디렉터리 삭제 또는 재생성
- 기존 `stepN.md` 파일 덮어쓰기 (이미 내용이 있는 경우)
- `phases/index.json` 또는 `phases/{task}/index.json` 초기화

**새 세션에서 작업을 시작할 때의 올바른 순서:**
1. `phases/index.json` 읽기 → 전체 phase 상태 파악
2. `phases/project-manifest.json` 읽기 (있으면) → 전체 프로젝트 누적 현황 파악
3. 첫 `pending` phase의 `phases/{task}/index.json` 읽기
4. 첫 `pending` phase의 `module-map.json` 읽기 (있으면)
5. 첫 `pending` step의 `stepN.md` 읽기
6. 작업 시작
