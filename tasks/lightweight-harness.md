# Lightweight harness

## 목표와 범위

프레임워크의 기본 사용을 짧은 프로젝트 규칙과 작업당 하나의 기록으로 경량화한다.
잘못된 기본 hooks를 제거하고 기존 phases 이력과 선택적 배치 도구를 보존한다.
프레임워크 저장소를 경량화하고 사용자 후속 요청으로 전역 harness 설치본과 번들도 동기화했다. 외부 제품 프로젝트는 변경하지 않았다.

## 완료 조건

- [x] 작은 작업에 phase/task와 모듈 페르소나를 강제하지 않는다.
- [x] 큰 작업을 tasks/{task}.md 하나로 기록한다.
- [x] Claude·Codex·Gemini·Kimi 진입점을 공통 경량 규칙에 맞춘다.
- [x] docs 전체 주입과 잘못된 기본 hooks를 제거한다.
- [x] 기존 phase 재스캐폴드 시 기록을 덮어쓰지 않는다.
- [x] 새 task CLI와 기존 도구 회귀 검증을 통과한다.

## 진행

- [x] 규칙·README·workflow·architecture·review 정리, legacy 안내 분리.
- [x] task 템플릿과 scaffold_task.py 추가.
- [x] 배치 프롬프트의 문서 일괄 주입 및 이중 커밋 지시 제거.
- [x] hooks 기본 비활성, Gemini의 없는 PRD 참조 제거.
- [x] phase scaffold 기존 상태 보호와 스모크 검사의 미설치 CLI 처리 수정.

## 주요 결정

- 에이전트의 기본 개발 루프·권한·컨텍스트 관리 기능을 사용한다.
- 작업 상태는 task 또는 기존 phase 한 곳에 기록한다.
- scripts/execute.py와 모듈 문서는 선택적 legacy 호환 기능으로 유지한다.
- Stop hook의 매 응답 전체 검증과 환경 변수 기반 명령 차단을 제거한다.
- 전역 설치본은 기존 공용 심볼릭 링크를 유지하며 스킬 진입점·번들·설치 저장소 진입 문서를 함께 갱신했다.

## 검증 결과

- `uv run --no-project --with pytest python -m pytest tests/ -q`: 46 passed.
- 시스템 `python3 -m pytest`는 pytest 미설치로 실행 불가. uv 환경에서 실제 실행했다.
- `python3 scripts/smoke_backends.py`: 사용 가능한 CLI의 help 검사 통과.
- Kimi는 실행 파일의 Python 인터프리터가 없어 skip. 명시적 선택 시 오류로 보고한다.
- hook JSON, Gemini TOML 파싱 통과. `git diff --check` 통과.
- 기존 MetaverseBridge phase 파일은 변경하지 않았다.
- 새 Codex/Claude 세션에서 hook 설정 반영은 별도로 실행 관찰하지 않았다.
- LLM 호출·배포·외부 프로젝트 실행은 수행하지 않았다.

## 다음 행동

구현과 전역 설치본 동기화 완료. 새 세션부터 경량 규칙을 사용한다.
스킬 frontmatter 검사 통과, 공용 도구 링크 4개와 번들 task CLI 동작 확인, 설치 번들 테스트 46개 통과.
이미 실행 중인 세션의 스킬 선택 설명은 이전 스냅샷일 수 있다.
