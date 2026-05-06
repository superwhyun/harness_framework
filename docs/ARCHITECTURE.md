> **Note:** 아래는 예시 프로젝트(FG-EAI)의 아키텍처 문서 템플릿입니다. 실제 사용 시 프로젝트 내용으로 교체하세요.

# 아키텍처: FG-EAI 하네스 (Harness)

## 디렉토리 구조
```text
/
├── docs/               # PRD, 아키텍처, ADR 등 전체 프로젝트 문서
├── .harness/           # 로컬 active project 상태
│   └── current_project # 현재 대상 프로젝트 경로 (git ignored)
├── projects/           # 산출 프로젝트 루트 (git ignored)
│   └── {project}/      # 독립 Git 저장소
│       ├── .git        # product 전용 Git 저장소
│       ├── phases/     # 페이즈별 작업 스텝 (작업 상태 관리)
│       │   ├── index.json
│       │   └── {task}/
│       │       ├── index.json
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

### 2. 세션 핸드오프 (Session Handoff)
각 단계 완료 후 `stepN-output.json`에 수행 결과, 변경 파일, 결정 사항, 다음 액션을 구조적으로 기록한다. 이를 통해 다음 세션의 AI 툴(Gemini, Claude 등)이 이전 대화 로그 없이도 즉시 작업을 재개한다.

### 3. 백엔드 추상화 (Backend Abstraction)
특정 AI 벤더 전용 명령이 아닌, 공통 인터페이스(`AgentBackend`)를 통해 다양한 AI CLI를 백엔드로 선택하여 실행할 수 있도록 한다.

## 데이터 흐름
```text
1. 사용자 요청 (Harness Command)
2. 대상 프로젝트 결정 (`.harness/current_project` 또는 사용자 입력)
3. 대상 프로젝트의 phases/index.json 탐색 (진행 중인 Phase 확인)
4. 대상 프로젝트의 phases/{task}/index.json 탐색 (첫 번째 pending 스텝 확인)
5. stepN.md 로드 (목표 및 AC 확인)
6. AI 에이전트 실행 (작업 수행 및 파일 수정)
7. 검증 (Validation script 실행)
8. 결과 기록 (stepN-output.json 생성 및 index.json 업데이트)
9. 핸드오프 (다음 세션 대기)
```

## 상태 관리
- **프레임워크 로컬 상태:** `.harness/current_project`
- **대상 프로젝트 전역 상태:** `phases/index.json`
- **대상 프로젝트 로컬 상태:** `phases/{task}/index.json`
- **전이 규칙:** `pending` -> `completed` (성공) / `error` (실패) / `blocked` (중단)
