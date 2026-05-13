# Harness Framework 개선 계획

> 작성 일시: 2026-05-07
> 대상: harness_framework 자체의 개선
> 방식: Harness Framework 워크플로우 준수 (phases/steps 구조)

---

## 1. Pull 후 변경사항 요약

`git pull` 결과 총 20개 파일이 변경/추가되었습니다.

**새로 추가된 파일:**
- `harness/project_context.py` — 활성 프로젝트 관리 (`projects/{project}/` 분리)
- `scripts/use_project.py` — active project 설정 CLI
- `.codex/hooks.json` — Codex용 PreToolUse/Stop 훅

**주요 개선된 부분:**
- `AGENTS.md`: 대상 프로젝트 결정 순서, handoff 기록 규칙, phase 마감 규칙(git tag, phases/index.json 동기화) 추가
- `README.md`: 툴 사용법(Antigravity 추가), 디렉터리 구조, 대상 프로젝트 개념 강화
- `docs/HARNESS.md`: 워크플로우 상세화 (대상 프로젝트 → 탐색 → 논의 → 설계 → 실행 → 핸드오프 → 커밋)
- `harness/executor.py`: `framework_root` 지원, harness.json 로딩 예외 처리, git repo 확인 추가
- `scripts/execute.py`: `resolve_project_root` 연동
- `scripts/scaffold_phase.py`, `validate_phase.py`: `resolve_project_root` 연동
- `scripts/phase_utils.py`: JSON read/write 예외 처리, validate 시 error/blocked 상태용 필드 검증 추가

---

## 2. 개선사항 재체크 (이전 vs 현재)

| # | 이전 이슈 | 상태 | 비고 |
|---|----------|------|------|
| 1 | **stepN-output.json 생성 미구현** | **미해결 (P0)** | `_execute_single_step()`에서 여전히 작성하지 않음 |
| 2 | **.gitignore vs tracked files 충돌** | **미해결 (P0)** | `docs/PRD.md` 등 4개 문서 + `harness.json` 여전히 충돌 |
| 3 | **auto_push dead code** | **미해결 (P0)** | `self._auto_push` 저장만 하고 `_finalize()`에 push 로직 없음 |
| 4 | 이전 에러 placeholder | 미해결 (P1) | `executor.py:333` 여전히 동일 |
| 5 | bare `except: pass` | 미해결 (P1) | `executor.py:279` 여전히 동일 |
| 6 | `_file_digest()` TOCTOU | 미해결 (P1) | `FileNotFoundError` 처리 없음 |
| 7 | Git checkout 실패 무시 | **부분 해결** | `rev-parse` 실패는 확인, `checkout` 실패는 여전히 무시 |
| 8 | CWD-의존적 import | 미해결 (P1) | `from phase_utils import ...` 여전히 동일 |
| 9 | `_top_index_file` 미사용 | 미해결 (P1) | `AGENTS.md`에 사용 규칙 추가됐으나 구현 없음 |
| 10 | `CHORE_MSG` 미사용 | 미해결 (P1) | 정의만 되어 있음 |
| 11 | FG-EAI 문서 혼재 | **부분 해결** | `project_context.py`로 "프레임워크 vs 대상 프로젝트" 분리. 단, 기존 문서는 repo에 남아있음 |
| 12 | `UI_GUIDE.md` 플레이스홀더 | 미해결 (P2) | 여전히 템플릿만 존재 |
| 13 | 테스트 파일 소스와 혼재 | 미해결 (P2) | `scripts/test_*.py` 여전히 동일 위치 |
| 14 | 통합 테스트 부재 | 미해결 (P2) | 추가된 테스트 없음 |
| 15 | StepExecutor God Class | 미해결 (P2) | 363라인, 여전히 과도한 책임 |
| 16 | 워크스페이스 스냅샷 비효율 | 미해결 (P2) | 해싱 캐싱 없음 |
| 17 | `harness.json` 프로젝트 정체성 | **부분 해결** | `framework_root` 검색 추가. 단 `"project": "FG-EAI"` 여전히 존재 |
| 18 | 백엔드 가드레일 불균형 | 미해결 (P2) | claude만 설정 |
| 19 | 문서 우선순위 불일치 | **미해결** | `AGENTS.md`에 `HARNESS.md` 여전히 누락 |
| 20 | `.claude/settings.json` Node.js 가정 | 미해결 (P3) | 여전히 `npm run lint/build/test` |
| 21 | `harness/__init__.py` 빈 파일 | 미해결 (P3) | 여전히 빈 파일 |
| 22 | `check_requirements.py` 하드코딩 | 미해결 (P3) | 여전히 동일 |

**새로 발견된 이슈:**
- `AGENTS.md`에 `HARNESS.md`가 문서 우선순위에 없음 (`README.md`와 불일치 지속)
- `AGENTS.md`에 추가된 "Phase 마감 시 git tag / phases/index.json 업데이트" 규칙이 `executor.py`에 미구현
- `.gitignore`에 `phases/*/` 추가됨 — 이는 대상 프로젝트용이나 프레임워크 루트에 `phases/`를 두게 되면 충돌 가능

---

## 3. 개선 계획 개요 (Harness Workflow)

본 개선 계획은 Harness Framework의 원칙을 따릅니다.

- 작업은 **phase 단위**로 분할하고, 각 phase는 **step 단위**로 쪼갭니다.
- 각 step에는 **읽을 파일, 작업, Acceptance Criteria, 검증 절차, 금지사항**이 포함됩니다.
- phase 완료 시 `git tag`를 생성합니다.
- 개선 계획 문서는 `phases/{phase}/stepN.md`에 위치합니다.

### Phase 구성

| Phase | 이름 | 목표 | Step 수 |
|-------|------|------|---------|
| 0 | `0-core-recovery` | 핵심 기능 복구: handoff JSON, auto_push, gitignore 충돌 | 3 |
| 1 | `1-robustness` | 견고성 강화: 예외 처리, dead code, import 경로 | 3 |
| 2 | `2-structure` | 구조 개선: 리팩토링, 테스트 분리, 문서 정리 | 3 |
| 3 | `3-security` | 보안 및 표준화: 플래그, 필터, 가드레일 | 3 |

---

## 4. Phase 상세

### Phase 0: core-recovery (핵심 기능 복구)

**핵심 목표:** 프레임워크의 핵심 가치인 "크로스툴 세션 핸드오프"가 작동하도록 만든다.

**Steps:**
1. `step0` — `handoff-json-writer`: `_execute_single_step()` 완료 후 `stepN-output.json` 자동 생성
2. `step1` — `auto-push-cleanup`: `--push` 플래그를 실제 동작시키거나 제거
3. `step2` — `gitignore-conflict-fix`: tracked & ignored 동시 적용 파일 해결

**Phase 마감 조건:**
- [ ] `stepN-output.json`이 step 완료 시 자동 생성된다.
- [ ] `git status`에서 tracked/ignored 충돌이 사라진다.
- [ ] `auto_push`가 동작하거나 노출되지 않는다.

**Phase 완료 후 태그:** `git tag harness-framework-phase0-done`

---

### Phase 1: robustness (견고성 강화)

**핵심 목표:** 예외 처리를 구체화하고, dead code를 정리하며, 스크립트 실행을 robust하게 만든다.

**Steps:**
1. `step0` — `exception-hardening`: bare `except: pass` 제거, TOCTOU 방지, git 실패 검사
2. `step1` — `dead-code-cleanup`: `CHORE_MSG`, `_top_index_file`, `prev_error` placeholder 처리
3. `step2` — `script-import-fix`: CWD-의존적 import를 robust하게 수정

**Phase 마감 조건:**
- [ ] `grep -r "except: pass" harness/` 결과가 0건이다.
- [ ] `python3 scripts/scaffold_phase.py --help`가 repo 루트 외부에서도 실행 가능하다.
- [ ] `_checkout_branch()`에서 checkout 실패 시 명확한 에러를 출력한다.

**Phase 완료 후 태그:** `git tag harness-framework-phase1-done`

---

### Phase 2: structure (구조 개선)

**핵심 목표:** God Class를 분리하고, 테스트를 재배치하며, 문서를 정리한다.

**Steps:**
1. `step0` — `executor-refactor`: `StepExecutor`를 GitManager/WorkspaceSnapshot/PromptBuilder/HandoffWriter로 분리
2. `step1` — `test-relocation`: `tests/` 디렉토리 생성 및 통합 테스트 추가
3. `step2` — `document-cleanup`: 문서 우선순위 일치, UI_GUIDE 정리, FG-EAI 문서 헤더 추가

**Phase 마감 조건:**
- [ ] `StepExecutor`가 200라인 이하로 축소되었다.
- [ ] `python -m pytest tests/`가 통과한다.
- [ ] `AGENTS.md`와 `README.md`의 문서 읽기 순서가 일치한다.

**Phase 완료 후 태그:** `git tag harness-framework-phase2-done`

---

### Phase 3: security (보안 및 표준화)

**핵심 목표:** 백엔드 기본값을 보수화하고, 위험 명령 필터를 프레임워크 레벨로 이동하며, 가드레일을 균형화한다.

**Steps:**
1. `step0` — `backend-flag-hardening`: dangerous 플래그 기본값 변경, `dangerous_mode` opt-in 설정 추가
2. `step1` — `dangerous-command-filter`: `harness/safety.py` 추가, 모든 백엔드에 적용
3. `step2` — `guardrail-balance`: 모든 백엔드에 `AGENTS.md` 가드레일 기본 적용, 없는 파일 참조 제거

**Phase 마감 조건:**
- [ ] 기본 백엔드 플래그에 `--dangerously-*` 또는 `--approval-mode yolo`가 없다.
- [ ] `rm -rf /` 패턴이 `GenericCommandBackend`에서 차단된다.
- [ ] `codex`, `gemini`, `kimi` 백엔드도 `guardrail_files`에 `AGENTS.md`를 포함한다.

**Phase 완료 후 태그:** `git tag harness-framework-phase3-done`

---

## 5. 실행 순서 및 의존성

```
Phase 0 (core-recovery)
  ├── Step 0: handoff-json-writer
  ├── Step 1: auto-push-cleanup
  └── Step 2: gitignore-conflict-fix
       ↓
Phase 1 (robustness)
  ├── Step 0: exception-hardening
  ├── Step 1: dead-code-cleanup
  └── Step 2: script-import-fix
       ↓
Phase 2 (structure)
  ├── Step 0: executor-refactor  ← Phase 0-0 (handoff writer) 선행 권장
  ├── Step 1: test-relocation    ← Phase 0, 1 완료 후 권장
  └── Step 2: document-cleanup
       ↓
Phase 3 (security)
  ├── Step 0: backend-flag-hardening
  ├── Step 1: dangerous-command-filter
  └── Step 2: guardrail-balance
```

**권장 워크플로우:**
1. Phase 0부터 순차적으로 진행한다.
2. 각 step 완료 후 `stepN-output.json`을 작성하고 커밋한다.
3. Phase 마감 시 `phases/index.json` 상태를 `completed`로 업데이트하고 `git tag`를 단다.
4. Phase 2의 `test-relocation`은 Phase 0, 1의 변경사항이 안정화된 후 실행하는 것이 유리하다.

---

## 6. 다음 액션 (Next Actions)

**즉시 시작 가능한 작업:**

```bash
# 1. 현재 phase 상태 확인
python3 scripts/validate_phase.py 0-core-recovery

# 2. Phase 0 Step 0부터 시작
# (AI 에이전트가 harness_framework 리포를 연 상태에서)
# "phases/0-core-recovery/step0.md를 읽고 handoff-json-writer를 구현해"
```

**사전 준비:**
- `harness.json`의 `"project"` 값을 `"harness-framework"`로 변경하는 것이 이 개선 작업의 첫 커밋이 될 수 있다.
- `.gitignore` 수정을 먼저 하면 `docs/PRD.md` 등의 변경사항이 `git status`에 잡히기 시작한다.

---

*본 계획은 Harness Framework의 phase/step 구조를 따르며, 실제 개선 작업의 진행은 `phases/{phase}/stepN.md` 문서를 기준으로 수행된다.*
