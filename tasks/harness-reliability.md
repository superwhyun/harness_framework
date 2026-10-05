# Harness reliability

## 목표와 범위

강한 코딩 모델이 작업에 맞게 설계·구현·검증하도록 가벼운 공통 흐름을 보강하고, 선택적 phase 실행기의 완료 판정·재시도·Git·컨텍스트 처리를 안정화한다.
기존 미커밋 경량화 변경과 phase 이력을 보존한다. 모델 버전이나 개발 순서를 고정하지 않는다.

## 완료 조건

- [x] 작업 규모에 맞는 설계와 검증, 진전 기반 반복, 단일 작업 기록을 공통 지침에 반영한다.
- [x] 실패 종료·미완료 step·검증 누락을 배치 완료로 처리하지 않는다.
- [x] 무의미한 재시도와 규칙·전체 프로젝트 현황의 반복 주입을 줄인다.
- [x] 사용자 변경·실행 기록을 보호하고 오류 원인 및 재개 방법을 남긴다.
- [x] 회귀 테스트와 mock CLI 통합 실행으로 성공·실패·재개를 확인한다.

## 진행

- [x] 기존 변경과 실행 경로, 회귀 테스트, 설치 스킬 구조 확인.
- [x] 실행기와 백엔드, 프롬프트, Git 보강.
- [x] 기본 workflow·템플릿·도구 진입점 정리.
- [x] 검증 및 결과 기록.
- [x] 전역 설치본의 관련 번들·스킬 진입점 동기화 및 기존 링크 확인.

## 주요 결정

- 인터랙티브 개발 루프는 도구가 담당한다. 별도 planner나 자동 모델 라우팅을 추가하지 않는다.
- 새로 실행하는 step은 검증 근거 또는 명시적 실행 checks를 요구한다. 기존 완료 이력은 소급 변경하지 않는다.
- 자동 Git 관리는 깨끗한 작업 트리에서만 시작한다. 미커밋 작업 재개에는 Git 관리를 끄는 명시적 옵션을 제공한다.
- 규칙 자동 로딩 백엔드는 파일 참조를 사용하고, 사용자 정의 백엔드는 본문 주입을 선택할 수 있다.
- 의존 step은 전이 관계까지 요약을 전달한다. 관련 없는 과거 이력과 전체 manifest는 경로를 통해 필요할 때 확인한다.
- 완료는 정상 종료·요약·해당 시도의 검증 근거 또는 독립 checks 통과 후에만 저장한다. 에이전트의 다른 step 완료 처리와 검사 약화를 거부한다.
- 실제 실패 원인과 변경 진전에 따라 재시도한다. 3회는 배치 비용 상한이며 의무 반복이 아니다.
- CLI 실행 권한은 Claude acceptEdits / Codex workspace-write를 기본으로 한다. 사용자 전역 설정과 모델 선택은 변경하지 않는다.
- 전역 설치 위치: `/Users/whyun/.agents/skills/harness/skills/harness`. 코드·문서 번들과 SKILL.md를 갱신하고 Codex·Claude·Kimi·Gemini의 기존 공용 링크를 유지했다. 외부 프로젝트 데이터는 변경하지 않았다.

## 검증 결과

- 변경 전: uv 환경 46 passed. 시스템 Python에는 pytest 없음.
- 변경 후: `uv run --no-project --with pytest python -m pytest tests/ -q`: **76 passed** (12.70초).
- 최종 help 플래그 보강 후: `tests/test_smoke_backends.py`: **2 passed**. CLI help 검사 통과, Kimi는 인터프리터 누락으로 skip.
- 실제 CLI subprocess + Git + 독립 checks를 사용하는 회귀 시나리오 통과. 최종 메타데이터 커밋, 실패 후 재개, 완료 후 재실행의 무변경을 확인했다.
- **GPT-6.1 Sol 실호출**: 별도 임시 저장소에서 clamp 구현 → 하네스 독립 검사 4개 통과 → phase 완료. 30.9초, 백엔드 종료 코드 0.
- **Claude Opus 5.5 실호출**: 응답 modelUsage의 `claude-opus-5-5` 확인. 같은 독립 검사 4개 통과 → phase 완료. 14.8초, 종료 코드 0, permission_denials 0.
- 실모델 검증은 작은 기능 하나의 호출·편집·상태 기록·검사 연동을 확인한 것이다. 대규모 개발 품질 비교나 실제 토큰 절감률을 측정한 것은 아니다.
- JSON/TOML 파싱, 스킬 quick_validate, 설치 번들 바이트 일치, 설치본 task 생성 및 executor help 확인 통과. `git diff --check` 통과.
- Codex CLI 0.160.0 / Claude Code 2.1.288의 현재 help와 [Codex 비대화형 실행 문서](https://learn.chatgpt.com/docs/non-interactive-mode)를 대조했다.
- 현재 저장소 및 설치 저장소의 커밋·push는 수행하지 않았다. 실호출 검증의 Git 변경은 폐기되는 임시 저장소에만 생성했다.

## 다음 행동

완료. 새 작업은 기존 자연어 요청 또는 harness 스킬로 진행한다. legacy 배치에서 새로 실행하는 step은 docs/LEGACY.md의 checks 또는 verification 계약을 사용한다.
