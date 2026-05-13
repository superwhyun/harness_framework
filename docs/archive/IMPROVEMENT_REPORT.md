# Harness Framework 개선 보고서

> 분석 일시: 2026-05-07
> 대상 저장소: https://github.com/superwhyun/harness_framework.git
> 분석 범위: 전체 코드베이스 및 문서

---

## 1. 개요 (Executive Summary)

Harness Framework는 복잡한 개발 작업을 `stepN.md` 단위로 분할하고, JSON 상태 파일을 통해 진행 상황을 추적하며, Claude Code / Codex / Gemini CLI / Kimi Code CLI 등 다양한 AI 코딩 도구 간 핸드오프를 가능하게 하는 **멀티 에이전트 AI 코딩 워크플로우 프레임워크**입니다.

**전반적 평가:**

| 항목 | 평가 | 요약 |
|------|------|------|
| 개념/설계 | ★★★★★ | 워크플로우 분할 및 크로스툴 핸드오프 아이디어가 우수함 |
| 문서화 | ★★★☆☆ | 구조는 좋으나 프로젝트 특이적 콘텐츠와 템플릿 혼재 |
| 코드 품질 | ★★★☆☆ | Python 스타일은 깔끔하나 미구현 기능과 취약한 예외 처리 다수 |
| 기능 완성도 | ★★☆☆☆ | 핵심 루프는 동작하나 **크로스툴 핸드오프(JSON 출력)가 미구현** |
| 테스트 커버리지 | ★★☆☆☆ | 유틸리티 단위 테스트만 존재, 핵심 루프 통합 테스트 부재 |
| 멀티 에이전트 지원 | ★★★★☆ | 백엔드 추상화는 깔끔하나 가드레일 설정 불균형 |
| 보안 | ★★☆☆☆ | 기본값이 과도하게 permissive, Claude 전용 안전 장치만 존재 |

**가장 심각한 문제:** `stepN-output.json` 생성 로직이 미구현되어 있어, 프레임워크의 **핵심 가치인 세션 간 안전한 핸드오프가 작동하지 않습니다.**

---

## 2. 심각도별 이슈 분류

### P0 — 반드시 즉시 수정해야 할 이슈

#### 2.1 stepN-output.json 생성 미구현 (핵심 기능 부재)

- **위치:** `harness/executor.py`
- **현상:** `_execute_single_step()`에서 step 실행 후 `stepN-output.json`을 **전혀 작성하지 않음**
- **영향:** 이전 step의 결과를 다음 에이전트/툴이 읽을 수 없어 **크로스툴 세션 재개 메커니즘이 물 걸 넘어감**
- **근거:** `_build_resume_context()`는 해당 파일을 읽으려 하나, 파일이 생성되지 않아 항상 빈 컨텍스트로 시작함
- **권장:** `HARNESS_GENERALIZATION_PROPOSAL.md`에 정의된 10개 이상의 필드(summary, files_changed, verification, known_issues, next_actions 등)를 포함한 JSON 자동 생성 로직 구현

#### 2.2 .gitignore vs tracked files 충돌

- **위치:** `.gitignore` (라인 16-20, 30)
- **현상:** 아래 파일들이 **Git에 추적(tracked)되어 있으면서 동시에 .gitignore에 의해 무시(ignored) 처리**됨
  - `docs/PRD.md`
  - `docs/ARCHITECTURE.md`
  - `docs/ADR.md`
  - `docs/UI_GUIDE.md`
  - `harness.json`
- **영향:** `git status`에 변경 사항이 표시되지 않아 개발자가 의도치 않게 변경을 놓칠 수 있음
- **권장:** 프로젝트 템플릿 용도라면 `.gitignore`에서 제거하거나, 샘플 파일로 남길 것인지 명확히 결정

#### 2.3 auto_push 파라미터 — 저장만 하고 사용 안 함 (Dead Code)

- **위치:** `harness/executor.py:73, 79`
- **현상:** CLI `--push` 플래그를 통해 `auto_push=True`가 전달되고 `self._auto_push`에 저장되나, **어디에서도 참조되지 않음**
- **영향:** 사용자가 `--push`를 지정핻도 실제 `git push`가 발생하지 않음 — 예상과 다른 동작
- **권장:** `_finalize()` 또는 `_execute_single_step()` 종료 시 `auto_push`가 `True`면 `git push` 실행하거나, 미지원 기능이라면 파라미터 제거

---

### P1 — 빠른 시일 내 수정 권장

#### 2.4 이전 에러 메시지 추출 실패 시 Placeholder 반환

- **위치:** `harness/executor.py:311`
- **현상:** 재시도 시 실제 이전 에러 대신 하드코딩된 한국어 메시지 전달
- **영향:** 백엔드가 실패 원인을 제대로 파악하지 못해 동일한 오류를 반복할 가능성
- **권장:** `index.json` 파싱 실패 시에도 stderr/stdout 로그에서 실제 에러를 추출하여 전달

#### 2.5 Bare except: pass — 예외 무기명 삼킴

- **위치:** `harness/executor.py:257`
- **현상:** `except: pass` 형태로 모든 예외를 묵살
- **영향:** JSON 디코드 에러, 파일 누락, 권한 문제 등 **모든 예외가 묵살**되어 디버깅 불가
- **권장:** 최소한 `except (json.JSONDecodeError, FileNotFoundError, PermissionError):`로 한정하고 로깅 추가

#### 2.6 _file_digest() — TOCTOU 레이스 컨디션

- **위치:** `harness/executor.py:181-183`
- **현상:** `_workspace_files()`로 파일 목록을 얻은 뒤 `_file_digest()`를 호출하는 사이 파일이 삭제되면 `FileNotFoundError` 발생
- **영향:** 워크스페이스 스냅샷 촬영 중 크래시
- **권장:** `try/except FileNotFoundError`로 감싸고, 삭제된 파일은 무시하거나 None으로 기록

#### 2.7 Git 명령 실패 무시

- **위치:** `harness/executor.py:170, 172`
- **현상:** `_checkout_branch()`에서 `git checkout` / `git checkout -b`의 반환값을 검사하지 않음
- **영향:** 브랜치 체크아웃 실패핗도 다음 단계로 넘어가며, 이후 모든 작업이 잘못된 브랜치에서 수행될 수 있음
- **권장:** `_run_git()` 반환값 검사 후 실패 시 예외 발생 또는 에러 상태 기록

#### 2.8 스크립트 간 CWD-의존적 import

- **위치:** `scripts/scaffold_phase.py`, `scripts/validate_phase.py`, `scripts/smoke_backends.py`
- **현상:** `from phase_utils import scaffold_phase` 또는 `import execute as ex` 등이 현재 작업 디렉토리에 의존
- **영향:** `python scripts/validate_phase.py` 형태로 실행하면 `ModuleNotFoundError`
- **권장:** `python -m scripts.validate_phase` 방식으로 실행하거나, `from scripts.phase_utils import ...`로 수정

#### 2.9 _top_index_file 초기화 후 미사용

- **위치:** `harness/executor.py:78`
- **현상:** `phases/index.json` 경로를 저장하나 executor가 **해당 파일을 읽거나 쓰지 않음**
- **영향:** 상위 phase 레지스트리가 완전히 무시됨
- **권장:** 전체 phase 목록 관리가 필요하면 구현하고, 불필요하면 제거

#### 2.10 CHORE_MSG 상수 — 정의만 되고 사용 안 함

- **위치:** `harness/executor.py:50`
- **현상:** `stepN-output.json` 커밋 메시지용으로 보이나 실제로는 `FEAT_MSG`만 사용
- **권장:** `stepN-output.json` 커밋 시 `CHORE_MSG` 사용하거나 제거

---

### P2 — 중기 개선 권장

#### 2.11 프로젝트 특이적 문서가 프레임워크 템플릿에 혼재

- **위치:** `docs/PRD.md`, `docs/ARCHITECTURE.md`, `docs/ADR.md`
- **현상:** FG-EAI(Embodied AI) 프로젝트 내용이 그대로 포함됨
- **영향:** 이 저장소가 프레임워크 템플릿인지 FG-EAI 프로젝트인지 모호함
- **권장:** FG-EAI 내용을 별도 브랜치/저장소로 분리하거나 `examples/fg-eai/` 디렉토리로 이동

#### 2.12 docs/UI_GUIDE.md — 템플릿 플레이스홀더만 존재

- **위치:** `docs/UI_GUIDE.md`
- **현상:** 모든 디자인 원칙, 색상, 컴포넌트, 레이아웃 값이 `{예: ...}`, `{원칙 1}` 형태
- **권장:** 실제 가이드라인으로 작성하거나, 프레임워크의 범위에서 벗어난다면 제거

#### 2.13 테스트 파일이 소스와 동일 디렉토리에 혼재

- **위치:** `scripts/test_*.py`
- **현상:** `test_execute.py`, `test_phase_tools.py`, `test_smoke_backends.py`가 `scripts/` 아래에 위치
- **영향:** 관심사 분리 위배
- **권장:** 프로젝트 루트에 `tests/` 디렉토리 생성 후 이동 (pytest 표준 구조)

#### 2.14 핵심 로직에 대한 통합 테스트 부재

- **현상:**
  - `StepExecutor.run()` 통합 테스트 없음
  - 재시도 로직(`MAX_RETRIES`) 테스트 없음
  - `_execute_single_step()` Mock 백엔드 테스트 없음
  - Git 브랜치 전환 테스트 없음
  - 핸드오프 JSON 생성/파싱 테스트 없음
- **권장:** Mock 백엔드를 활용한 `StepExecutor` 통합 테스트 스위트 작성

#### 2.15 StepExecutor — 과도한 책임 집중 (God Class)

- **위치:** `harness/executor.py` (341라인)
- **현상:** Git 조작, 워크스페이스 해싱, 가드레일 로딩, 백엔드 호출, 프롬프트 빌드, 진행 상태 표시, 브랜치 관리 등 **모든 것을 한 클래스에서 처리**
- **권장:** `GitManager`, `WorkspaceSnapshot`, `PromptBuilder`, `HandoffWriter` 등으로 분리

#### 2.16 워크스페이스 스냅샷 비효율

- **위치:** `harness/executor.py`
- **현상:** 매 step 실행 전 **모든 추적 파일에 대해 SHA-256 해싱**을 동기적으로 수행. 캐싱 없음.
- **권장:** `git ls-files` 결과가 변하지 않았다면 해시 재사용, 또는 `git diff --name-only`로 변경 파일만 해싱

#### 2.17 harness.json — 프레임워크 기본값과 프로젝트 정체성 혼합

- **위치:** `harness.json`
- **현상:** `"project": "FG-EAI"`가 하드코딩됨. Codex 백엔드의 가드레일 파일이 `.codex/AGENTS.md`를 참조하나 실제 파일은 `.claude/settings.json`만 존재.
- **권장:** `harness.json`에서 project 필드를 템플릿 값으로 변경, 가드레일 파일 경로를 실제 존재하는 파일로 수정

#### 2.18 백엔드 가드레일 설정 불균형

- **위치:** `harness.json`
- **현상:** `claude` 백엔드만 `guardrail_files`가 설정되어 있고, `codex`/`gemini`/`kimi`는 빈 배열
- **영향:** 다른 백엔드로 실행 시 AGENTS.md 규칙이 전달되지 않을 수 있음
- **권장:** 모든 백엔드에 동일한 가드레일 파일 목록 적용 (또는 백엔드별 최소 규칙 설정)

---

### P3 — 권장 사항 (선택적)

#### 2.19 문서 우선순위 불일치

- **현상:**
  - `AGENTS.md` 읽기 순서: AGENTS → PRD → ARCHITECTURE → ADR → UI_GUIDE → phases
  - `README.md` 읽기 순서: AGENTS → HARNESS → PRD → ARCHITECTURE → ADR → UI_GUIDE → phases
  - `HARNESS.md`가 `AGENTS.md` 우선순위 목록에 누락
- **권장:** 두 문서의 읽기 순서를 일치시키고 `HARNESS.md`를 `AGENTS.md`에 추가

#### 2.20 .claude/settings.json — Node.js 스택 가정

- **위치:** `.claude/settings.json`
- **현상:** Stop hook이 `npm run lint && npm run build && npm run test`를 실행
- **영향:** Python/기타 프로젝트에서 해당 프레임워크를 사용할 때 매번 실패
- **권장:** `package.json` 존재 여부를 확인하는 조건부 실행으로 변경

#### 2.21 harness/__init__.py — 빈 파일

- **위치:** `harness/__init__.py`
- **현상:** 패키지 레벨 export가 없어 `from harness import StepExecutor` 등이 불가
- **권장:** `__all__`에 `StepExecutor`, `AgentBackend`, `GenericCommandBackend` 등 주요 클래스 노출

#### 2.22 check_requirements.py — 하드코딩된 phase 이름

- **위치:** `scripts/check_requirements.py`
- **현상:** `phase_dir_name="2-ai-requirements-validator"`가 하드코딩되고 `data/requirements.json` 존재를 가정
- **권장:** 명령줄 인수로 phase 디렉토리 이름을 받도록 변경

---

## 3. 보안 관련 우려

### 3.1 과도하게 permissive한 기본 백엔드 플래그

| 백엔드 | 플래그 | 위험도 |
|--------|--------|--------|
| Claude | `--dangerously-skip-permissions` | 높음 — 모든 권한 요청 스킵 |
| Codex | `--dangerously-bypass-approvals-and-sandbox` | 높음 — 승인 및 샌드박스 우회 |
| Gemini | `--approval-mode yolo` | 높음 — 자동 승인 |
| Kimi | `--print` | 중간 — yolo 모드 암시적 활성화 |

- **권장:** 기본값을 보수적인 모드로 변경하고, `harness.json`에서 각 프로젝트가 명시적으로 opt-in하도록 설정

### 3.2 Claude 전용 위험 명령 필터

- **위치:** `.claude/settings.json`
- **현상:** `rm -rf`, `git push --force`, `DROP TABLE` 등의 정규표현식 필터가 Claude에만 적용됨
- **영향:** Gemini, Kimi, Codex 사용자는 동일한 보호를 받지 못함
- **권장:** `harness/executor.py`의 `GenericCommandBackend` 실행 전에 프레임워크 레벨에서 위험 명령 필터 적용

### 3.3 GenericCommandBackend 프롬프트 인젝션 가능성

- **위치:** `harness/backends/generic.py`
- **현상:** step 프롬프트 전체가 명령 배열에 직접 보간됨
- **분석:** `subprocess.run(shell=False)`이므로 셸 인젝션은 방지되나, 백엔드 명령 템플릿이 `--flag`, `{prompt}` 형태라면 악성 프롬프트가 CLI 플래그 주입 가능
- **권장:** 프롬프트를 파일로 저장한 뒤 파일 경로만 전달하거나, argparse-safe 인코딩 적용

---

## 4. 권장 개선 로드맵

### Phase 1: 핵심 기능 복구 (1-2일)
1. `stepN-output.json` 자동 생성 로직 구현 (summary, files_changed, verification, known_issues, next_actions 필드 포함)
2. `.gitignore`와 tracked files 충돌 해결
3. `auto_push` 미구현 — 구현 또는 제거
4. Bare `except: pass` 구체화 및 로깅 추가

### Phase 2: 견고성 강화 (2-3일)
5. `_file_digest()`, `_checkout_branch()`, `_run_git()` 에러 핸들링 강화
6. 스크립트 import 경로 수정 (`python -m scripts.xxx` 또는 상대 import)
7. `_top_index_file`, `CHORE_MSG` 등 dead code 정리
8. `prev_error` placeholder → 실제 에러 추출

### Phase 3: 구조 개선 (3-5일)
9. FG-EAI 특이 문서를 `examples/` 또는 별도 브랜치로 분리
10. `docs/UI_GUIDE.md` 완성 또는 제거
11. 테스트를 `tests/` 디렉토리로 이동
12. `StepExecutor`를 `GitManager`, `WorkspaceSnapshot`, `PromptBuilder`, `HandoffWriter`로 분리
13. `harness/__init__.py`에 패키지 export 추가

### Phase 4: 보안 및 테스트 (3-5일)
14. 백엔드 기본 플래그를 보수적 모드로 변경, `harness.json`에서 opt-in 가능하도록 설정
15. 프레임워크 레벨 위험 명령 필터 구현 (모든 백엔드에 적용)
16. Mock 백엔드를 활용한 `StepExecutor.run()` 통합 테스트 작성
17. 재시도 로직, Git 브랜치 전환, 핸드오프 JSON 파싱 테스트 추가

---

## 5. 결론

Harness Framework는 **멀티 에이전트 AI 코딩 워크플로우라는 훌륭한 개념**을 가지고 있으며, `HARNESS_GENERALIZATION_PROPOSAL.md`에 담긴 설계 사상은 매우 탄탄합니다. 하지만 현재 코드베이스는 **핵심 기능인 핸드오프 메커니즘이 미완성**인 상태이며, 예외 처리, 테스트 커버리지, 보안 기본값 등에서 다소 미흡한 부분이 존재합니다.

가장 중요한 것은 **Phase 1의 `stepN-output.json` 구현**입니다. 이 기능이 작동해야 비로소 Claude에서 시작해 Kimi로 이어가기 같은 프레임워크의 핵심 가치가 실현됩니다. 이를 우선적으로 완성한 뒤, 점진적으로 견고성과 보안을 강화해 나가는 것을 권장합니다.

---

*본 보고서는 저장소의 모든 주요 파일을 정적 분석하여 작성되었습니다.*
