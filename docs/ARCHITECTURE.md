# Architecture

## 기본 구성

- `AGENTS.md`: 에이전트 공통 프로젝트 규칙.
- `templates/task.md.tmpl`: 큰 작업의 목표·완료 조건·진행·검증·재개 기록.
- `scripts/scaffold_task.py`: 지정한 저장소에 task 하나를 생성. 기존 기록을 덮어쓰지 않는다.
- `tasks/{task}.md`: 명시적 단위별 범위·의존 관계·완료 조건·검증 결과와 현재 상태. 현재 에이전트 세션이 단위별로 수행하며 외부 모델 호출은 없다.
- 도구별 진입 파일: 공통 규칙과 필요할 때만 읽는 workflow로 연결.

개발 흐름은 사용자 요청 → 필요한 탐색과 계획 → 구현 → 검증 → 기록 갱신이다.
구현·검증·컨텍스트 압축·권한은 현재 에이전트와 도구가 담당한다. 하네스 지침은 단위별 순서와 검증 결과를 명시하도록 하고, 스캐폴드는 기록 틀만 생성한다.
작은 작업에는 task 파일을 요구하지 않는다. 큰 작업도 하나의 기록을 사용한다.

## 정보의 기준

- 코드·타입·스키마: 실제 동작과 공개 계약.
- task 또는 기존 phase: 현재 진행과 재개 정보.
- Git: 변경 이력.
- architecture/ADR: 코드만으로 드러나지 않는 구조와 중요한 결정.

module persona, registry, module-map, baseline, project-manifest를 기본 작업에 생성하거나 동기화하지 않는다.
병렬 작업에 필요한 소유권은 해당 작업에서만 정한다.

## Legacy 호환

`harness/`와 phase 관련 scripts/templates는 기존 프로젝트용으로 유지한다.
`PromptBuilder`는 기본 CLI의 지침 자동 로딩을 활용하고 누락된 규칙만 읽도록 안내한다. 사용자 정의 백엔드는 inline 주입을 지원한다. 전체 manifest·누적 step 요약을 자동 주입하지 않는다.
문서, 모듈 계약, baseline은 해당 step에서 필요할 때 읽는다.
배치 실행기는 정상 종료, step 상태와 검증 근거를 확인한다. checks를 지정하면 직접 실행한다. 실패에는 원인과 재개 방법을 기록하고, 진전 없는 재시도를 중단한다. Git 자동 관리 시 기존 변경이 없는지 확인하며 상태 JSON은 원자적으로 저장한다. 프로젝트 CI나 백엔드 도구 권한을 대체하지 않는다.
자세한 사용법은 `docs/LEGACY.md`에 있다.

## Hooks

`.claude/settings.json`과 `.codex/hooks.json`의 hooks는 비어 있다.
응답 종료 시 자동 전체 검증과 환경 변수 기반 명령 차단을 사용하지 않는다.
