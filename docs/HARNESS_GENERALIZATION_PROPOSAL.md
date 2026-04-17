# 범용 하네스 전환 변경안

## 목적

현재 하네스는 `scripts/execute.py` 가 `claude` CLI와 `CLAUDE.md` 에 직접 결합되어 있어 Claude 전용에 가깝다.
이 변경안의 목적은 아래를 만족하는 범용 하네스로 전환하는 것이다.

- 같은 `phases/{task}/stepN.md` 워크플로우를 유지한다.
- Claude, Codex, Gemini Code, Kimi Code CLI를 실행 백엔드로 선택할 수 있게 만든다.
- 공통 규칙과 에이전트별 보조 규칙을 분리한다.
- 기존 Claude 사용자는 큰 사용법 변화 없이 계속 쓸 수 있게 한다.
- 세션이 종료된 뒤 다음 세션에서 다른 툴로 안전하게 재개할 수 있게 만든다.

## 지원 범위 명확화

이 변경안이 보장하려는 것은 "작업 도중 실시간 툴 전환"이 아니다.
지원 범위는 아래다.

- 한 세션이 끝난 뒤 다음 세션에서 다른 AI 툴로 이어서 작업
- 이미 완료된 step 이후 다음 pending step 부터 재개
- 실패한 step 을 handoff 기록을 보고 다른 툴로 재시도

지원 범위에서 제외하는 것은 아래다.

- 하나의 step 실행 도중 다른 툴로 즉시 갈아타기
- 동일한 미완료 수정 상태를 두 툴이 번갈아 직접 이어받기
- 툴 내부 hook/tool-use 동작까지 완전히 동일하게 맞추기

즉 이 설계의 핵심은 "백엔드 자유 전환" 자체보다 "세션 종료 시점의 handoff 품질"이다.

## 현재 결합 지점

### 1. 실행기 결합

`scripts/execute.py` 는 현재 아래를 전제로 동작한다.

- `_load_guardrails()` 가 `CLAUDE.md` 만 읽는다.
- `_invoke_claude()` 가 `claude -p --dangerously-skip-permissions --output-format json` 를 직접 호출한다.
- 출력 파일 이름과 로그 문구도 Claude 기준이다.

이 구조에서는 Codex/Gemini를 붙이려 해도 실행 경로를 새로 복붙해야 한다.

### 2. 워크플로우 문서 결합

`.claude/commands/harness.md`, `.claude/commands/review.md` 에 범용 워크플로우가 들어 있는데 경로가 Claude 전용이다.
실제 내용은 Claude 전용이 아니라 하네스 전반의 동작 설명에 가깝다.

### 3. 검증/보호장치 결합

`.claude/settings.json` 의 hooks 는 Claude에서는 유효하지만 Codex/Gemini에서 그대로 재사용되지 않는다.
즉 안전장치가 에이전트 플랫폼 기능에 묶여 있다.

## 목표 상태

### 핵심 원칙

- `step` 포맷은 공통 자산으로 유지한다.
- 실행 백엔드만 교체 가능하도록 분리한다.
- 공통 문서는 벤더 중립 경로에 둔다.
- 에이전트별 설정은 선택적 shim 으로만 유지한다.

### 목표 구조

```text
AGENTS.md                     # 공통 프로젝트 규칙 (canonical)
docs/
  HARNESS.md                 # 공통 워크플로우 문서
  REVIEW.md                  # 공통 리뷰 절차 문서
  ...
.claude/
  commands/
    harness.md               # docs/HARNESS.md 를 가리키는 Claude shim
    review.md                # docs/REVIEW.md 를 가리키는 Claude shim
  settings.json              # Claude 전용 편의 설정
.codex/
  config.toml                # Codex 전용 선택 설정
.gemini/
  settings.json              # Gemini 전용 선택 설정
scripts/
  execute.py                 # 얇은 CLI 엔트리포인트
  harness/
    __init__.py
    config.py                # 하네스 설정 로더
    context.py               # 공통 문서/가드레일 수집
    executor.py              # StepExecutor 본체
    backends/
      base.py                # AgentBackend 인터페이스
      claude.py              # Claude CLI 어댑터
      codex.py               # Codex CLI/SDK 어댑터
      gemini.py              # Gemini CLI/SDK 어댑터
      kimi.py                # Kimi Code CLI 어댑터
tests/
  test_execute.py
  test_backends.py
  test_context.py
```

## 제안 아키텍처

### 1. 실행 백엔드 추상화

새 인터페이스를 둔다.

```python
class AgentBackend(Protocol):
    name: str

    def invoke(self, prompt: str, *, cwd: str, timeout: int) -> BackendResult:
        ...
```

`BackendResult` 는 아래 필드를 가진다.

- `exit_code`
- `stdout`
- `stderr`
- `raw_command`
- `parsed_payload` optional

이렇게 하면 `StepExecutor` 는 "누가 실행했는지" 대신 "프롬프트를 실행하고 결과를 받는다" 만 알면 된다.

단, 이 추상화는 "세션 경계에서 재개"를 위한 것이다.
백엔드 간 실시간 상태 공유까지 책임지지 않는다.

### 2. 하네스 설정 파일 도입

루트에 `harness.json` 또는 `harness.yaml` 을 추가한다. JSON이 현재 코드베이스와 더 잘 맞으므로 1차 제안은 `harness.json` 이다.

예시:

```json
{
  "default_backend": "claude",
  "backends": {
    "claude": {
      "command": ["claude", "-p", "--dangerously-skip-permissions", "--output-format", "json"]
    },
    "codex": {
      "command": ["codex", "exec", "--json"]
    },
    "gemini": {
      "command": ["gemini", "--prompt", "{prompt}"]
    },
    "kimi": {
      "command": ["kimi", "--print", "--output-format", "stream-json", "-p", "{prompt}"]
    }
  },
  "context": {
    "common_files": ["AGENTS.md", "docs/*.md"],
    "backend_files": {
      "claude": ["CLAUDE.md"],
      "codex": [".codex/AGENTS.md"],
      "gemini": [".gemini/AGENTS.md"]
    }
  }
}
```

포인트는 CLI 세부 옵션을 코드가 아니라 설정에 둔다는 점이다.

### 3. 공통 규칙과 에이전트별 규칙 분리

권장 순서는 아래와 같다.

- `AGENTS.md` 를 공통 규칙의 canonical 파일로 승격
- `CLAUDE.md` 는 Claude 보조 규칙만 남기거나 `AGENTS.md` 요약/shim 으로 축소
- Codex/Gemini/Kimi 전용 보조 규칙이 필요하면 `.codex/AGENTS.md`, `.gemini/AGENTS.md`, `.kimi/AGENTS.md` 추가

`_load_guardrails()` 도 아래 순서로 읽도록 바꾼다.

1. 공통 규칙: `AGENTS.md`
2. 공통 문서: `docs/*.md`
3. 선택 백엔드 보조 규칙: `CLAUDE.md` 또는 `.codex/AGENTS.md` 등

이렇게 해야 특정 벤더 문서가 없어도 공통 하네스는 동작한다.

### 4. 공통 워크플로우 문서의 중립화

현재 `.claude/commands/harness.md` 와 `.claude/commands/review.md` 는 내용상 공통 문서다.
이를 아래처럼 재배치한다.

- `docs/HARNESS.md`
- `docs/REVIEW.md`

그리고 `.claude/commands/*.md` 는 아래처럼 얇은 shim 으로 바꾼다.

- "실제 워크플로우는 `/docs/HARNESS.md` 를 따르라"
- "실제 리뷰 절차는 `/docs/REVIEW.md` 를 따르라"

이 방식이면 Claude에서는 기존 진입점이 유지되고, 다른 에이전트도 같은 원문을 참조할 수 있다.

### 5. 플랫폼 종속 안전장치의 실행기 이동

현재 PreToolUse/Stop hook 에 있는 보호장치 중 핵심은 플랫폼 밖으로 옮겨야 한다.

실행기로 이동할 항목:

- 위험 명령어 차단
- step 종료 후 `lint/build/test` 실행
- 실패 시 에러 메시지를 다음 retry 프롬프트에 주입

플랫폼에 남길 항목:

- 각 벤더가 제공하는 UX 편의 설정

이렇게 하면 Claude hooks 가 없는 환경에서도 동일한 최소 안전장치를 확보할 수 있다.

### 6. 세션 handoff 기록 강화

세션이 끝난 뒤 다른 툴로 이어서 작업하려면 `summary` 한 줄만으로는 부족하다.
현재 `phases/{task}/index.json` 구조는 유지하되, 각 step output 에 아래 구조화 정보를 남겨야 한다.

권장 필드:

- `status`: `completed` | `error` | `blocked`
- `summary`: 이번 step 에서 실제로 끝난 일 한 줄 요약
- `completed_work`: 완료된 작업 목록
- `files_changed`: 생성/수정/삭제 파일 목록
- `decisions`: 이번 step 에서 확정된 설계 결정
- `verification`: 실행한 명령과 결과 요약
- `known_issues`: 아직 남은 문제
- `next_actions`: 다음 세션이 바로 수행해야 할 일
- `blockers`: 사용자 개입 필요 사항
- `resume_hint`: 다음 세션이 먼저 읽어야 할 파일

예시:

```json
{
  "step": 2,
  "name": "api-layer",
  "status": "completed",
  "summary": "API client와 기본 에러 매핑을 추가하고 통합 테스트를 통과시켰다.",
  "completed_work": [
    "ApiClient 인터페이스 추가",
    "HTTP 에러를 도메인 에러로 변환하는 매퍼 구현",
    "기본 통합 테스트 4개 작성 및 통과"
  ],
  "files_changed": [
    "src/services/api_client.ts",
    "src/services/errors.ts",
    "tests/api_client.test.ts"
  ],
  "decisions": [
    "재시도 정책은 호출자 레이어에서 담당하고 client 는 순수 request/response 만 처리"
  ],
  "verification": {
    "commands": [
      "npm test -- tests/api_client.test.ts",
      "npm run build"
    ],
    "result": "pass"
  },
  "known_issues": [],
  "next_actions": [
    "service layer에서 ApiClient를 주입하도록 wiring",
    "timeout 설정을 환경변수로 분리"
  ],
  "blockers": [],
  "resume_hint": [
    "phases/0-mvp/step3.md",
    "src/services/api_client.ts",
    "tests/api_client.test.ts"
  ]
}
```

이 기록이 있으면 다음 세션의 AI 툴은 이전 대화가 없어도 현재 상태를 비교적 안정적으로 복원할 수 있다.

### 7. 재개 프롬프트 표준화

다음 세션에서 다른 툴로 재개할 때는 이전 대화 로그에 의존하지 말고, 아래 정보만으로 재개하도록 강제하는 편이 안전하다.

1. `AGENTS.md`
2. `docs/*.md`
3. 현재 step 파일
4. 직전 completed/error step 의 `stepN-output.json`
5. 최신 `git status` 와 현재 브랜치

즉 "대화 히스토리 전달"보다 "저장된 작업 상태 전달"을 표준 경로로 삼아야 한다.

## 파일별 변경안

### 수정

- `scripts/execute.py`
  - CLI 파싱만 담당하도록 축소
  - `--backend <claude|codex|gemini|kimi>` 추가
  - 기본값은 `harness.json` 의 `default_backend`
  - step 종료 시 구조화된 handoff output 저장

- `scripts/test_execute.py`
  - `_invoke_claude()` 중심 테스트를 백엔드 추상화 테스트로 교체
  - 공통 가드레일 로딩 순서 테스트 추가
  - handoff output 필드 검증 테스트 추가

- `AGENTS.md`
  - 공통 규칙 문서로 정리
  - Claude 전용 표현 제거

- `CLAUDE.md`
  - 선택 문서로 축소하거나 deprecated 안내 추가

- `.claude/commands/harness.md`
  - 범용 문서로 이동 후 shim 화

- `.claude/commands/review.md`
  - 범용 문서로 이동 후 shim 화

### 추가

- `harness.json`
- `scripts/harness/config.py`
- `scripts/harness/context.py`
- `scripts/harness/executor.py`
- `scripts/harness/backends/base.py`
- `scripts/harness/backends/claude.py`
- `scripts/harness/backends/codex.py`
- `scripts/harness/backends/gemini.py`
- `scripts/harness/backends/kimi.py`
- `docs/HARNESS.md`
- `docs/REVIEW.md`
- `tests/test_backends.py`
- `tests/test_context.py`
- `tests/test_handoff.py`

## CLI 변경안

### 기존

```bash
python3 scripts/execute.py 0-mvp
python3 scripts/execute.py 0-mvp --push
```

### 변경 후

```bash
python3 scripts/execute.py 0-mvp
python3 scripts/execute.py 0-mvp --backend claude
python3 scripts/execute.py 0-mvp --backend codex
python3 scripts/execute.py 0-mvp --backend gemini
python3 scripts/execute.py 0-mvp --backend kimi
python3 scripts/execute.py 0-mvp --push
```

기본값은 `default_backend` 를 쓰므로 기존 Claude 사용자는 그대로 실행 가능해야 한다.

## 검증된 백엔드 명령

2026-04-18 기준으로 아래 명령을 기본값으로 채택한다.

- Claude: `claude -p --dangerously-skip-permissions --output-format json "{prompt}"`
- Codex: `codex exec --json --dangerously-bypass-approvals-and-sandbox "{prompt}"`
- Gemini: `gemini --approval-mode yolo --output-format json "{prompt}"`
- Kimi: `kimi --print --output-format stream-json -p "{prompt}"`

검증 근거:

- 로컬 설치 CLI의 `--help` 출력
- OpenAI Codex 공식 문서의 `codex exec` / `--json` / 비대화식 실행 가이드
- Gemini CLI 공식 headless 문서의 `--output-format json` / `--approval-mode` 가이드
- Kimi Code CLI 공식 print mode 문서의 `--print` / `--output-format stream-json` 가이드

주의:

- Codex의 `--dangerously-bypass-approvals-and-sandbox` 와 Claude의 `--dangerously-skip-permissions`, Gemini의 `--approval-mode yolo` 는 모두 자동 실행을 위한 공격적인 설정이다.
- Kimi의 `--print` 는 비대화식 모드이며 문서상 `--yolo` 를 암묵적으로 활성화한다.
- 즉 "세션 handoff와 비대화식 실행" 목적에는 맞지만, 더 보수적인 운영을 원하면 프로젝트별로 `harness.json` 에서 완화해야 한다.

## 하위호환 전략

### 1단계 호환

초기 전환에서는 기존 사용자를 깨지 않기 위해 아래를 유지한다.

- 기본 백엔드 = `claude`
- `CLAUDE.md` 가 있으면 계속 읽음
- `.claude/commands/*` 유지
- 기존 step 포맷 유지
- 기존 `summary` 기반 흐름 유지, 단 output JSON 에 구조화 handoff 필드 확장

### 2단계 정리

충분히 이행된 뒤 아래를 진행한다.

- `CLAUDE.md` 의 역할 축소
- `.claude/commands/*` 를 문서 shim 으로 단순화
- 하네스 사용 설명의 canonical 위치를 `docs/HARNESS.md` 로 고정

## 테스트 전략

### 단위 테스트

- `config.py`: 기본 백엔드, 설정 override, 잘못된 백엔드 처리
- `context.py`: 공통 문서 + 백엔드 문서 병합 순서
- `backends/*.py`: 명령 생성과 결과 파싱
- `executor.py`: retry, blocked, error, completed 상태 전이
- handoff builder: `files_changed`, `next_actions`, `verification` 저장 형식

### 통합 테스트

- mock backend 로 step 실행
- backend 별 stdout/stderr 저장 형식 검증
- `--backend` 옵션에 따른 분기 검증
- Claude로 step 1 완료 후 Codex로 step 2 재개되는 흐름 검증
- Gemini로 실패한 step 을 이전 output JSON 기반으로 재시도하는 흐름 검증

### 회귀 테스트

- 현재 Claude 실행 경로가 이전과 동일하게 동작하는지 보장
- 기존 `phases/index.json` 포맷이 깨지지 않는지 검증

## 리스크와 대응

### 리스크 1. 각 CLI의 출력 형식이 다름

대응:

- `BackendResult` 로 normalize
- 파싱 실패 시 raw stdout/stderr 를 그대로 저장

### 리스크 2. 플랫폼별 권한/인터랙션 모델 차이

대응:

- executor 는 non-interactive 모드만 지원
- backend 설정에 필수 플래그를 선언
- 인터랙티브 의존 기능은 범용 경로에서 제외

### 리스크 2-1. "툴을 바꿨더니 직전 맥락이 날아감"

대응:

- 대화 맥락이 아니라 handoff JSON 을 기준 상태로 삼음
- 다음 세션 프롬프트는 직전 output JSON 을 필수 입력으로 포함
- 다음 step 시작 전에 `resume_hint` 파일을 먼저 읽게 강제

### 리스크 3. 문서 중복으로 규칙이 분산됨

대응:

- 공통 규칙의 canonical 위치를 `AGENTS.md` 로 고정
- 에이전트별 파일은 supplement 로만 사용

### 리스크 4. Claude hooks 제거 시 안전성 저하

대응:

- 필수 안전장치는 Python executor 로 이관
- hooks 는 보조 기능으로만 유지

## 권장 마이그레이션 순서

### Phase 1. 추상화 골격 도입

- `scripts/harness/` 패키지 추가
- `AgentBackend` 와 `ClaudeBackend` 도입
- `execute.py` 를 얇은 엔트리포인트로 분리
- 기존 테스트를 보존한 채 리팩터링

### Phase 2. 공통 문서 경로 정리

- `docs/HARNESS.md`, `docs/REVIEW.md` 추가
- `.claude/commands/*` 를 shim 으로 변경
- `AGENTS.md` 를 공통 canonical 규칙 문서로 정리

### Phase 3. 다중 백엔드 추가

- `CodexBackend`, `GeminiBackend`, `KimiBackend` 추가
- `--backend` 옵션 활성화
- `harness.json` 도입

### Phase 4. 안전장치 이관

- 위험 명령 차단을 executor 로 이동
- 종료 시 검증 명령 실행을 executor 로 이동
- Claude hooks 는 선택 기능으로 축소

## 구현 우선순위

가장 먼저 해야 할 일은 `execute.py` 의 Claude 직접 호출을 추상화하는 것이다.
이 부분을 먼저 분리하지 않으면 나머지 문서 정리나 설정 추가는 전부 겉포장에 그친다.

즉 우선순위는 아래가 맞다.

1. 실행 백엔드 추상화
2. 공통/에이전트별 문서 분리
3. 설정 파일 도입
4. Codex/Gemini 어댑터 추가
5. hooks 의 실행기 이관

## 최종 판단

이 리포는 "step 문서 기반 자가 실행 하네스" 라는 핵심 아이디어 자체는 범용적이다.
문제는 실행기와 진입 문서가 Claude 이름에 직접 묶여 있다는 점이다.

따라서 전체를 새로 갈아엎을 필요는 없다.
다음 두 축만 분리하면 된다.

- 공통 워크플로우 자산 vs 에이전트별 보조 자산
- StepExecutor vs 실제 LLM 실행 백엔드

이 변경안대로 가면 기존 Claude 사용자 경험을 유지하면서 Codex/Gemini Code용 어댑터를 점진적으로 붙일 수 있다.
다만 성공 조건은 "언제든 실시간 전환"이 아니라 "세션이 끝난 뒤 다른 툴이 구조화된 기록만으로 안정적으로 재개"하는 것이다.
