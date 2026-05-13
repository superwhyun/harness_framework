# 아키텍처: Harness Framework

## 디렉토리 구조
```text
/
├── docs/               # 아키텍처, ADR, 워크플로우 문서
├── .harness/           # 로컬 active project 상태
│   └── current_project # 현재 대상 프로젝트 경로 (git ignored)
├── projects/           # 산출 프로젝트 루트 (git ignored)
│   └── {project}/      # 독립 Git 저장소
│       ├── .git        # product 전용 Git 저장소
│       ├── phases/     # 페이즈별 작업 스텝 (작업 상태 관리)
│       │   ├── index.json
│       │   ├── baselines/
│       │   │   └── {phase-dir}.json
│       │   └── {task}/
│       │       ├── index.json
│       │       ├── module-map.json
│       │       ├── stepN.md
│       │       └── stepN-output.json
│       └── 실제 코드
├── scripts/            # 하네스 엔진 및 유틸리티 (Harness Engine)
│   ├── execute.py      # 범용 실행기 (Backend Agnostic)
│   ├── scaffold_phase.py # 페이즈 뼈대 생성 (Automation)
│   └── validate_phase.py # 정합성 검증 (Validation)
└── templates/          # 스텝 및 페이즈 표준 템플릿
```

## 패턴
### 1. 단계별 분해 (Step-based Decomposition)
복잡한 작업을 원자 단위의 `Step`으로 분해하여, AI 에이전트가 각 단계의 `Acceptance Criteria(AC)`에만 집중하게 함으로써 오류를 최소화한다.

### 2. 계약 우선 모듈 경계 (Contract-first Module Boundary)
각 phase는 `module-map.json`으로 모듈, 소유 step, `owned_paths`, public contract, dependency를 기록한다. 후속 step은 이전 구현 전체를 다시 읽지 않고 baseline과 public contract를 먼저 읽는다. 품질상 구현 확인이 필요할 때만 영향 모듈을 targeted read 한다.

### 3. 세션 핸드오프 (Session Handoff)
각 단계 완료 후 `stepN-output.json`에 수행 결과, 변경 파일, 결정 사항, 다음 액션을 구조적으로 기록한다. 이를 통해 다음 세션의 AI 툴(Gemini, Claude 등)이 이전 대화 로그 없이도 즉시 작업을 재개한다.

`stepN-output.json`은 복구용 기록이며, 후속 개발의 기본 입력은 `module-map.json`, `phases/baselines/{phase-dir}.json`, public contract다.

### 4. 백엔드 추상화 (Backend Abstraction)
특정 AI 벤더 전용 명령이 아닌, 공통 인터페이스(`AgentBackend`)를 통해 다양한 AI CLI를 백엔드로 선택하여 실행할 수 있도록 한다.

## 데이터 흐름
```text
1. 사용자 요청 (Harness Command)
2. 대상 프로젝트 결정 (`.harness/current_project` 또는 사용자 입력)
3. 대상 프로젝트의 phases/index.json 탐색 (진행 중인 Phase 확인)
4. 대상 프로젝트의 phases/{task}/index.json 탐색 (첫 번째 pending 스텝 확인)
5. 이전 phase baseline과 현재 phase module-map 로드 (있으면)
6. stepN.md 로드 (목표, 모듈 경계, AC 확인)
7. AI 에이전트 실행 (작업 수행 및 파일 수정)
8. blocked step을 해소하는 blocking-fix가 있으면 우선 실행
9. 검증 (Validation script 실행)
10. 결과 기록 (stepN-output.json 생성 및 index.json 업데이트)
11. Phase 완료 시 baseline artifact 생성
12. 핸드오프 (다음 세션 대기)
```

## 상태 관리
- **프레임워크 로컬 상태:** `.harness/current_project`
- **대상 프로젝트 전역 상태:** `phases/index.json`
- **대상 프로젝트 로컬 상태:** `phases/{task}/index.json`
- **모듈 경계 상태:** `phases/{task}/module-map.json`
- **Phase 기준선:** `phases/baselines/{phase-dir}.json`
- **전이 규칙:** `pending` -> `completed` (성공) / `error` (실패) / `blocked` (중단)
- **Blocking fix 규칙:** pending `blocking-fix` step은 일반 pending step보다 먼저 실행되고, 완료 시 `unblocks` 대상 step을 다시 `pending`으로 돌린다.
