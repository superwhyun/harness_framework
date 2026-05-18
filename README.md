# Harness Framework 🚀

하네스 프레임워크는 작업을 원자 단위의 `Step`으로 분해하고, 세션이 중단되더라도 다양한 AI 코딩 에이전트(Antigravity, Gemini, Claude, Kimi 등)가 상태를 안전하게 공유하며 이어서 작업할 수 있도록 지원하는 **범용 하네스 워크플로우 인프라**입니다.

이 프레임워크는 무한 자동화 루프 대신 **"구조화된 작업 기록과 안전한 세션 재개"**를 핵심 가치로 삼습니다.

---

## 🌟 핵심 패러다임

### 1. 계약 우선 개발 (Contract-first Development)
토큰 소모를 극대화하는 전체 코드 재탐색 방식을 지양하고, **계약(Contract)**과 **기준선(Baseline)**을 중심으로 협업합니다.
* **`module-map.json` 도입**: 각 페이즈(Phase)는 모듈 경계, 소유 step, `owned_paths`, `public contracts`, `dependencies`를 선언하여 범위를 제한합니다.
* **토큰 절약 우선**: 후속 step은 의존 모듈의 구현 전체를 다시 읽는 대신, 이전 페이즈의 `baseline`과 해당 모듈의 `public contract`를 먼저 읽습니다.
* **Surgical Edit (Surgical 수정)**: 품질이나 AC 검증을 위해 소스코드를 직접 조회해야 할 경우에는 영향이 있는 모듈만 targeted read로 최소화하여 분석합니다.
* **격리된 문제 해결**: contract에 불일치나 변경이 필요한 경우, 현재 작업 중인 step에 억지로 섞어 수정하지 않고 `blocking-fix` 또는 `contract-change` step을 명시적으로 추가(append)하여 해결합니다.

### 2. 프로젝트 매니페스트 누적 시스템 (`project-manifest.json`)
여러 페이즈가 완료될 때마다 전체 프로젝트의 구성 요소를 자동으로 수집하여 단일 매니페스트로 통합 관리합니다.
* 페이즈 마감 시 `phases/project-manifest.json` 파일에 모듈 현황, 라우트(중복 제거), 공유 계약, 외부 통합 지점(Integration Points) 및 전체 완료 이력(`tag`, `completed_at` 등)이 자동으로 누적 및 갱신됩니다.
* 새로운 페이즈를 시작하는 에이전트는 이 통합 매니페스트 파일 하나만 읽어 전체 프로젝트의 구조적 진척 상황을 즉시 이해할 수 있습니다.

---

## 🛡️ CRITICAL: phases/ 디렉터리 보호 규칙

`phases/` 디렉터리는 프로젝트 구현 계획과 진행 상태를 관리하는 **유일한 진실 공급원 (SSOT, Single Source of Truth)**입니다. 아래의 행동은 프로젝트 상태를 파괴하므로 **절대 금지**됩니다.

> [!WARNING]
> * **프로젝트 디렉터리(`projects/{project-name}/`)를 삭제하거나 다시 생성하지 마십시오.**
> * **`phases/` 디렉터리와 하위 상태 파일들을 삭제하거나 초기화하지 마십시오.**
> * **이미 존재하고 내용이 기록된 기존 `stepN.md`를 덮어쓰지 마십시오.**
> * 프로젝트 소스코드가 없거나 `package.json`이 누락되었더라도 `phases/` 디렉터리가 존재한다면 이는 **진행 중인 프로젝트**입니다. 절대로 scaffold를 다시 실행하지 마십시오.

### 🔄 새 세션 시작 시 올바른 탐색 프로세스
새로운 협업 세션을 시작할 때, 모든 에이전트는 반드시 아래의 **7단계 순서**대로 상태를 탐색해야 합니다.

1. **`phases/index.json` 읽기** ➔ 프로젝트 전체 페이즈 목록과 완료/진행 상태 파악
2. **`phases/project-manifest.json` 읽기 (존재 시)** ➔ 누적된 프로젝트 모듈 및 아키텍처 상태 파악
3. **첫 `pending` 페이즈의 `phases/{task}/index.json` 읽기** ➔ 해당 페이즈의 세부 step 목록 파악
4. **페이즈의 `module-map.json` 읽기 (존재 시)** ➔ 모듈 소유권 및 계약 경계 파악
5. **첫 `pending` step의 `stepN.md` 지시서 읽기** ➔ 구현 범위와 AC(Acceptance Criteria) 확인
6. **직전 완료 step의 `stepN-output.json` 읽기** ➔ (필요 시) 세션 복구를 위한 힌트 획득
7. **실제 작업 실행 착수**

---

## 🛠️ CRITICAL: Git 관리 및 .gitignore 규칙

하네스 프레임워크 하위의 개별 프로젝트들은 각각 독립적인 Git 저장소로 관리됩니다. 상태 손상과 무분별한 파일 추적을 방지하기 위해 엄격한 Git 규칙을 적용합니다.

> [!IMPORTANT]
> **1. `git init`은 단 한 번만 실행합니다.**
> * `git init`은 프로젝트 최초 scaffold step 시점에 **딱 1회만** 실행되어야 합니다.
> * 디렉터리 내에 `.git` 디렉터리가 이미 존재한다면 어떠한 경우에도 `git init`을 재실행해서는 안 됩니다.
> 
> **2. 첫 `git add` 전에 반드시 `.gitignore`를 작성합니다.**
> * `.gitignore` 파일이 구성되지 않은 상태에서 `git add .` 또는 `git add -A`를 실행하는 것은 절대 금지됩니다.
> * 기술 스택에 맞춰 아래의 기본 템플릿 요소를 필수로 포함해야 합니다:
>   ```text
>   # 의존성 및 런타임
>   node_modules/
>   .venv/
>   __pycache__/
>   *.pyc
> 
>   # 빌드 및 컴파일 산출물
>   dist/
>   build/
>   *.tsbuildinfo
> 
>   # 환경 변수 및 설정
>   .env
>   .env.local
>   .env.*.local
>   .vscode/
>   .idea/
>   .DS_Store
>   ```

### 📦 Step 단위 커밋 정책
* 커밋은 페이즈 단위가 아니라 **Step 단위**로 수행합니다.
* **커밋 위치**: 프레임워크 루트가 아닌 `projects/{project-name}/` 내의 **개별 프로젝트 Git 저장소**에서 실행해야 합니다.
* **커밋 시점**: 해당 Step의 AC를 모두 만족하고 검증을 통과하여 `stepN-output.json` 작성까지 완벽히 마친 직후.
* **커밋 메시지 규격 (Conventional Commits)**:
  ```text
  feat({project}/step{N}): {step-name} — {한 줄 요약}
  ```
  *(예시: `feat(debate/step0): project-setup — package skeleton`)*

---

## 🏁 Phase 완료 및 마감(Closure) 프로세스

특정 페이즈의 마지막 Step이 `completed`로 전환되면, 즉시 아래의 프로세스를 통해 페이즈를 공식 마감해야 합니다.

1. **상위 페이즈 상태 갱신**: `phases/index.json`에서 완료된 해당 페이즈의 `status`를 `completed`로 즉시 업데이트합니다.
2. **Baseline 아티팩트 작성**:
   다음 페이즈가 불필요하게 이전 소스코드를 전체 재탐색하지 않도록 `phases/baselines/{phase-dir}.json` 파일에 아래 내용을 요약 보강합니다:
   * 완료 태그 (Completion Tag)
   * 모듈 목록 및 Public Surface / Contracts
   * 공유 계약 및 API 라우트 정보
   * 외부 연동 포인트 (Integration Points) 및 알려진 이슈 (Known Issues)
3. **Git 태깅 완료**:
   마지막 step 커밋이 완료되면 프로젝트 저장소에 릴리즈 태그를 생성합니다:
   ```bash
   git tag {project}-phase{N}-done
   # 예시: git tag debate-phase0-done
   ```

---

## 📚 문서 우선순위 (Document Priority)

모든 AI 에이전트는 작업을 시작할 때 다음의 문서 읽기 순서를 엄격히 준수합니다.

```mermaid
graph TD
    A[1. AGENTS.md - Canonical Rules] --> B[2. docs/HARNESS.md - Workflow Specification]
    B --> C[3. docs/ARCHITECTURE.md - Design Map]
    C --> D[4. docs/ADR.md - Technical Decisions]
    D --> E[5. phases/project-manifest.json - Manifest Status]
    E --> F[6. phases/{task}/module-map.json - Module Contracts]
    F --> G[7. phases/{task}/stepN.md - Step Instruction]
```

> [!NOTE]
> 저장소의 절대적인 Canonical 표준 규칙은 **[AGENTS.md](file:///Users/whyun/workspace/harness_framework/AGENTS.md)**에 보존되며, 툴별 전용 설정 파일은 보조 수단으로만 기능합니다.

---

## 🤖 에이전트별 사용 가이드

### 1. Antigravity (IDE 통합 에이전트)
Antigravity는 IDE 내부에 고도로 융합된 에이전트로, 전역 시스템 설정(`~/.gemini/antigravity/`)을 로드하여 독립적으로 작동합니다.
* **동작 차이**: 터미널 단독 툴인 Gemini CLI와 달리, 로컬 리포지토리의 `.gemini/commands/*.toml` 설정이 자동완성 UI 커맨드로 직접 노출되지 않을 수 있습니다.
* **사용법**: UI 자동완성에 구애받지 않고 채팅 창에 아래 명령어나 자연어 프롬프트를 자유롭게 입력하여 실행하면 최적의 워크플로우를 완벽하게 작동시킵니다.
  ```text
  /harness
  /review
  ```
  *자연어 입력 예시: `harness 워크플로우 진행해줘`, `현재 코드의 변경사항 리뷰 수행해줘`*

### 2. Gemini CLI (터미널 단독 툴)
* 로컬 컨텍스트 파일: `.gemini/settings.json`
* 프로젝트 커맨드: `.gemini/commands/harness.toml`, `review.toml`
* 실행 방법: 터미널 창에서 직접 `/harness` 또는 `/review` 입력

### 3. Claude Code
* 프로젝트 규칙: `CLAUDE.md`
* 프로젝트 명령: `.claude/commands/harness.md`, `review.md`
* 실행 방법: `/harness` 또는 `/review` 입력

### 4. Kimi Code CLI
* 프로젝트 규칙: `AGENTS.md`
* 실행 방법: `/skill:harness` 또는 `/skill:review` 입력

### 5. Codex
* 별도의 슬래시 커맨드를 사용하지 않으며, `AGENTS.md`를 표준으로 삼아 자연어 명령으로 워크플로우를 요청합니다.
  *예시: `현재 phases 상태를 읽고 첫 pending step부터 진행해줘`*

---

## 🚀 빠른 시작 및 스크립트 도구 레퍼런스

### 1. 활성 프로젝트 설정 (`use_project.py`)
현재 작업할 대상 프로젝트를 지정하여 로컬 캐시(`.harness/current_project`)에 기록합니다.
```bash
python3 scripts/use_project.py projects/{project-name}
```

### 2. 새 페이즈 뼈대 생성 (`scaffold_phase.py`)
새로운 작업 페이즈를 설계하고 표준 스텝 파일 구조를 자동 생성합니다.
```bash
# active project가 .harness/current_project에 지정된 경우 (생략형)
python3 scripts/scaffold_phase.py {phase-dir} --project {name} --steps step1 step2

# active project 설정이 없는 경우 --root 명시
python3 scripts/scaffold_phase.py {phase-dir} --project {name} --steps step1 step2 --root projects/{project-name}
```

### 3. 페이즈 데이터 정합성 검증 (`validate_phase.py`)
작성되거나 수정된 페이즈 인덱스, 모듈 맵, 스텝 문서 스키마의 무결성을 검증합니다.
```bash
python3 scripts/validate_phase.py {phase-dir}
```

### 4. 백엔드 스모크 테스트 (`smoke_backends.py`)
로컬 컴퓨터에 설치된 백엔드 CLI 툴(Claude, Gemini, Kimi 등)의 인터페이스 및 도움말 명세가 하네스 연동 규격에 맞는지 확인합니다.
```bash
python3 scripts/smoke_backends.py
```

### 5. 배치 비대화식 실행기 (`execute.py`)
CI/CD 자동화 환경이나 로컬 배치 테스트 시 백엔드를 일괄 구동합니다. 일반적인 대화식 작업에서는 사용이 권장되지 않습니다.
```bash
python3 scripts/execute.py 0-mvp --backend gemini
```

> [!TIP]
> 하네스는 안전을 위해 보수적인 권한 모드로 동작합니다. CI/CD 등 자동화 환경에서 모든 권한 승인을 스킵하는 YOLO 모드를 실행하려면 `harness.json`에 `"dangerous_mode": true` 설정을 명시해야 합니다.

---

## 📁 디렉터리 구조 가이드

```text
.
├── AGENTS.md               # 전사 공통 코딩 에이전트 규칙 (Canonical Rules)
├── CLAUDE.md               # Claude Code Supplement
├── GEMINI.md               # Gemini / Antigravity Supplement
├── harness.json            # 배치 실행기 백엔드 및 보안 옵션 설정
├── docs/                   # 프레임워크 표준 지침 문서
│   ├── HARNESS.md          # 하네스 스텝 및 세션 라이프사이클 명세
│   ├── REVIEW.md           # 코드 품질 및 아키텍처 리뷰 표준 가이드
│   ├── ARCHITECTURE.md     # 프레임워크 및 데이터 흐름 아키텍처
│   └── ADR.md              # 아키텍처 주요 결정 이력
├── .harness/
│   └── current_project     # 현재 활성화된 프로젝트 경로 캐시
├── scripts/                # 하네스 자동화 및 유틸리티 엔진 스크립트
├── templates/              # scaffold 표준 마크다운 템플릿 소스
└── projects/               # 실제 개발 대상 개별 산출물 저장소 (Git Ignore 대상)
    └── {project-name}/
        ├── .git            # 제품 자체의 독립된 Git 저장소
        └── phases/         # 프로젝트 진행 상태를 기록하는 SSOT
            ├── index.json  # 페이즈 목록 및 상태
            ├── project-manifest.json # 누적 프로젝트 매니페스트
            ├── baselines/  # 완료 페이즈 아티팩트
            └── {phase-dir}/
                ├── index.json       # 스텝 목록 및 상태
                ├── module-map.json  # 모듈 경계, 소유 step, contracts
                ├── stepN.md         # 개별 스텝 수행 지시서
                └── stepN-output.json# 복구용 아티팩트
```

---

## 💡 권장 협업 및 운영 가이드
* **스텝 범위 격리**: 하나의 Step은 항상 명확하고 좁은 단일 책임 범위를 유지해야 합니다. 
* **구조화된 핸드오프**: 세션이 중단되거나 완료될 때는 반드시 `stepN-output.json`을 누락 없이 작성하여, 후속 에이전트가 완벽하게 바통을 이어받을 수 있게 합니다.
* **대화 맥락 의존 금지**: 이전 세션의 메신저 대화 이력에 의존하지 마십시오. 오직 파일 상태(`index.json`, `module-map.json`, `baseline`, `contract`)만이 유일한 진실입니다.
