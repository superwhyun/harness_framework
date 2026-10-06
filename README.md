# Lightweight Harness Framework

> **⚠️ 폐기됨 (2026-10-07)**
>
> Claude Code·Codex·Antigravity에 `/goal` 명령이 도입된 이후 이 프로젝트는 더 이상 의미가 없어 폐기한다.
> 이 하네스가 제공하던 "완료 조건까지 단위별로 구현·검증을 반복하는 실행 루프"는 `/goal`이,
> 계획 수립은 각 도구의 plan mode·`/plan`이 대체한다. 남은 가치인 작업 기록은 프레임워크 없이
> 대상 저장소의 `AGENTS.md` 규칙과 plain Markdown task 문서만으로 충분하다.
>
> 대신 이렇게 사용한다: plan mode로 단위·완료 조건을 확정한 뒤
> `/goal <결과> 완료: <검증 명령 출력 통과> 제약: <수정 범위·테스트 삭제/skip 금지> 막히면: <멈춤 조건>`.
> `/goal`과 함께 쓰는 마지막 정리는 [docs/HARNESS.md](docs/HARNESS.md)의 "/goal과 함께 쓰기"에 있다.
>
> 저장소는 기록용으로만 보존하며 더 이상 유지보수하지 않는다.

Codex, Claude Code, Gemini CLI, Kimi Code CLI가 작업을 이어받을 수 있도록 하는 가벼운 프로젝트 규칙과 작업 기록 템플릿이다.
탐색·설계·편집·검증은 현재 Claude·Codex 등의 세션에서 수행한다. 하네스는 명시적 실행 단위와 재개 기록을 제공하며 별도의 모델 CLI를 호출하지 않는다.

## 기본 사용

1. 대상 저장소의 `AGENTS.md`에 필요한 프로젝트 규칙과 검증 명령을 둔다.
2. 작은 수정은 바로 처리한다.
3. 큰 작업은 `tasks/{task}.md` 하나에 검증 가능한 실행 단위를 계획한다.
4. 같은 세션에서 각 단위를 구현·검증하고 통과 결과와 해당 변경을 커밋한 뒤 후속 단위와 마지막 통합 검증까지 진행한다.
5. 종료·인계 시 검증 결과, 남은 일, 다음 행동을 갱신한다.

현재 Claude·Codex에서 “하네스로 로그인 기능을 설계하고 개발해. 실행 단위로 나눠 검증하며 진행해”라고 요청한다.
기존 계획을 사용하거나 에이전트가 task를 작성한다. 선택적 스캐폴드는 문서만 생성한다.

```bash
python3 /path/to/harness_framework/scripts/scaffold_task.py login --root /path/to/existing-repo --units api ui integration
```

`--root` 생략 시 현재 디렉터리를 사용한다. 기존 파일은 덮어쓰지 않으며 모델 호출·Git 조작은 없다.
프로젝트를 이 프레임워크의 `projects/` 아래로 옮길 필요는 없다.

## 최소 구성

```text
AGENTS.md             프로젝트 규칙과 검증 명령
tasks/{task}.md       큰 작업의 계획·진행·검증·재개 기록
docs/ARCHITECTURE.md  필요한 경우에만 유지하는 구조 설명
```

모듈 페르소나, registry, baseline, manifest, 불필요한 고정 step 순서, 세션당 한 step,
phase 태그는 기본 흐름에서 요구하지 않는다. 검증된 의미 있는 step마다 커밋하며, 분리하면 동작하지 않는 작은 step은 묶는다. phase 종료 시 추가 변경이 있을 때만 커밋하고 push·태그는 별도 요청을 따른다.
타입·스키마·API 정의가 공개 계약의 기준이며, 이를 문서에 반복해서 복제하지 않는다.
기능 개발에서는 목표 동작·변경 경계·검증 방법을 정하고, 동작 가능한 단위로 구현과 검증을 이어간다.
모델 버전은 고정하지 않는다. Opus·GPT Sol급 코딩 모델의 설계 판단을 활용하고 검증 근거와 재개 정보를 남긴다.

## 도구 진입점

- Codex: `AGENTS.md`와 자연어 요청.
- Claude Code: `CLAUDE.md`에서 공통 규칙을 가져온다. `/harness`는 선택적 진입점이다.
- Gemini CLI: `.gemini/settings.json`에서 `AGENTS.md`를 읽는다. `/harness`는 선택 사항이다.
- Kimi Code CLI: `AGENTS.md`, 선택적 `/skill:harness`.

별도 진입 명령 없이 바로 작업을 요청해도 같은 규칙을 따른다.

## Hooks

기본 hook은 비활성이다. 변경 후 필요한 검증 명령을 명시적으로 실행한다.
권한은 각 도구의 permissions/sandbox에서 관리한다. 변경 이유는 [ADR](docs/ADR.md)에 기록한다.

## 기존 프로젝트

기존 `phases/` 이력과 코드는 보존한다. 재개가 필요한 경우 기존 도구를 선택적으로 사용한다.
배치 실행은 정상 종료와 검증 근거를 확인한다. 명시적 `checks`는 실행기가 직접 수행하며, 미커밋 작업은 `--no-commit`으로 이어간다.
[Legacy 도구](docs/LEGACY.md), [작업 흐름](docs/HARNESS.md), [설계](docs/ARCHITECTURE.md).

## 프레임워크 검증

```bash
python3 -m pytest tests/ -q
```

pytest가 없으면 `uv run --no-project --with pytest python -m pytest tests/ -q`로 실행할 수 있다.
