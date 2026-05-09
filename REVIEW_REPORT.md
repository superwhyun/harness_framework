# Harness Framework 개선 프로젝트 최종 리뷰

> 리뷰 일시: 2026-05-07
> 대상: Phase 0~4 전체 개선사항 (12 step)
> 상태: 25/25 테스트 통과

---

## 1. Git 이력 확인

| 항목 | 상태 | 내용 |
|------|------|------|
| 12개 step 커밋 | ✅ 완료 | `feat(harness-framework/step{N}): ...` 형식 일관됨 |
| 4개 phase 태그 | ✅ 완료 | `phase0-done` ~ `phase3-done` |
| 태그 매핑 | ⚠️ 참고 | `phase3-done`은 Phase 2의 마지막 커밋과 동일 (Phase 3 커밋이 없었음) |

---

## 2. Critical Issues (반드시 수정 필요)

### C1. `StepExecutor.__init__`에서 `sys.exit()` 호출

**파일:** `harness/executor.py`
**문제:** 생성자에서 유효성 검사 실패 시 `sys.exit(1)`을 호출함. 이는 클래스를 단위 테스트에서 에러 경로를 검증할 수 없게 만듦.
**해결:** 예외를 던지고(`ValueError`, `RuntimeError`), 호출자(`scripts/execute.py`)에서 exit code를 처리하도록 변경.

### C2. `harness.json`이 기본 가드레일을 덮어씀

**파일:** `harness.json` + `harness/executor.py`
**문제:** `harness.json`에 `guardrail_files: []`로 명시된 codex/gemini/kimi 백엔드가 `DEFAULT_BACKENDS`의 `AGENTS.md` 기본값까지 덮어씀.
```python
configs[name] = data  # 완전 대체 → guardrail_files 기본값 손실
```
**해결:** `_get_backend_configs()`에서 deep merge를 하거나, `harness.json`의 각 백엔드에 `"guardrail_files": ["AGENTS.md"]` 추가.

### C3. `smoke_backends.py`가 ollama/lmstudio를 테스트하지 않음

**파일:** `scripts/smoke_backends.py`
**문제:** `HELP_CHECKS`에 ollama/lmstudio가 정의되어 있으나 `available_backends()`는 `DEFAULT_BACKENDS.keys()`만 반환하여 실제로 테스트되지 않음.
**해결:** `available_backends()`에 ollama/lmstudio 추가 또는 `HELP_CHECKS`에서 제거.

### C4. `_execute_single_step`에서 백엔드 예외 미처리

**파일:** `harness/executor.py`, `harness/backends/generic.py`
**문제:** `invoke()`가 `subprocess.TimeoutExpired`, `FileNotFoundError`(바이너리 없음), `OSError`를 발생시킬 수 있으나 아무것도 잡지 않음. 예외가 상위로 전파되면 executor가 크래시됨.
**해결:** `invoke()` 호출을 try/except로 감싸고 재시도 가능한 실패로 처리.

### C5. `GitManager.commit_all`이 실패를 무시함

**파일:** `harness/git_manager.py`
**문제:** `git commit` 실패(empty commit, pre-commit hook, GPG) 시 return code를 확인하지 않고 넘어감.
**해결:** return code 검사 후 예외 발생 또는 boolean 반환.

---

## 3. Important Issues (수정 권장)

### I1. 커밋 메시지 형식 불일치

- **AGENTS.md:** `feat({project}/step{N}): {step-name} — {한 줄 요약}`
- **코드(executor.py):** `feat({phase}): step {num} — {name}`

둘 중 하나로 통일 필요.

### I2. Phase 완료 시 `git tag` 미구현

AGENTS.md에 `git tag {project}-phase{N}-done` 규칙이 있으나, `_finalize()`에 이 로직이 없음. 태그는 수동으로만 생성됨.

### I3. 진행 표시기 형식 버그

`Step {step_num}/{self._total - 1}` → 3 step일 때 `Step 0/2`로 표시되어 직관적이지 않음. `Step 1/3` 형태(1-based)로 변경 권장.

### I4. `StepExecutor.__init__`의 타입 불일치

`self._root = str(root)`(str)와 `self._phases_dir = root / "phases"`(Path)가 혼재. 다른 메서드에서 반복적으로 `Path(self._root)`로 변환함.

### I5. 통합 테스트에서 `os.system` 사용

`tests/test_executor_integration.py`의 `os.system(f"cd {root} && git init ...")`는 공백이 있는 경로에서 깨질 수 있음. `subprocess.run`으로 대체 권장.

### I6. `subprocess.run` 전역 monkeypatch

`test_git_checkout_failure_is_fatal`에서 `subprocess.run = fake_run`으로 전역 패치. `finally`로 복원하지만 테스트 중간에 예외가 나면 복원되지 않을 수 있음. `unittest.mock.patch` 사용 권장.

### I7. `WorkspaceSnapshot.list_files`가 git 실패를 묵살

`git ls-files` 실패 시 `[]` 반환. 빈 스냅샷이 캡처되어 실제 변경이 있어도 `diff`가 아무것도 잡지 못함.

### I8. `SafetyFilter` 패턴이 너무 좁음

- `rm\s+-rf\s+/`는 `rm -rf /home`, `rm -rf /*`를 놓침
- `git\s+push\s+--force`는 `git push -f`를 놓침
- 프롬프트 자체가 CLI 인자에 포함되므로, 백엔드가 낶적으로 생성한 위험 명령은 차단 불가 (아키텍처적 한계)

### I9. `test_smoke_backends.py` skip 조건이 너무 보수적

`REQUIRED_BINARIES` 중 하나라도 없으면 전체 테스트가 skip됨. 개발자가 Claude만 설치했을 때도 테스트 불가. 백엔드별 개별 skip 권장.

---

## 4. Minor Issues / 개선 제안

| # | 내용 | 위치 |
|---|------|------|
| M1 | `progress_indicator` 클리어 라인이 충분히 길지 않을 수 있음 (9999초 이상 시) | executor.py |
| M2 | `next_step_name or "phase complete"`가 빈 문자열 `""`일 때 `""`가 됨 | handoff_writer.py |
| M3 | `commit_all`이 이미 `git add -A`를 하므로 이전의 `self._git.add(...)`는 중복 | executor.py |
| M4 | `step{num}.md` 파일이 없으면 `FileNotFoundError` 미처리 | executor.py |
| M5 | `_write_json`이 non-serializable 객체에 대한 처리 없음 | executor.py |
| M6 | 대용량 바이너리 파일에 대한 해싱 시 메모리 부담 가능 | workspace.py |
| M7 | `FEAT_MSG`에 새 키 추가 시 `build_preamble`의 `.format()`에서 `KeyError` | prompt_builder.py |
| M8 | `render_template`가 단순 문자열 치환 (한 키 값이 다른 키 placeholder 포함 시 문제) | phase_utils.py |
| M9 | `__init__.py`에 `__all__` 부재로 public API 불명확 | harness/__init__.py |
| M10 | Phase 3 태그가 Phase 2 커밋을 가리킴 → 문서화 필요 | git tags |
| M11 | 에러 메시지가 한국어/영어 혼재 | 전반적 |

---

## 5. 잘된 점

### 아키텍처
- **관심사 분리가 우수함:** `GitManager`, `WorkspaceSnapshot`, `PromptBuilder`, `HandoffWriter`로 분리되어 가독성과 테스트성이 크게 향상됨
- **Protocol 기반 백엔드 설계:** `AgentBackend` + `BackendResult`로 Mock 백엔드 추가가 매우 쉬움
- **`pathlib` 일관 사용:** 대부분의 파일 조작이 `Path` 객체를 올바르게 사용함

### 보안
- **`dangerous_mode` opt-in 설계가 탁월함:** 기본값이 안전하고, aggressive 플래그는 명시적 설정 필요
- **`SafetyFilter` 프레임워크 레벨 통합:** 모든 백엔드에 균일하게 적용됨
- **재시도 로직에 에러 컨텍스트 전달:** 실패 시 다음 프롬프트에 이전 에러를 포함하여 자가 교정 가능

### 테스트
- **통합 테스트가 충분함:** Mock 백엔드로 상태 전이, 재시도, 출력 필드, git 실패를 모두 검증
- **smoke 테스트:** 실제 CLI 설치 여부를 확인
- **25/25 전부 통과**

### 문서
- **README가 매우 충실함:** 5개 툴(Claude, Codex, Gemini, Kimi, Antigravity) 모두 커버
- **AGENTS.md 구조화 우수:** 워크플로우, 파일 우선순위, 커밋 규칙이 명확
- **12개 커밋 메시지 형식 일관**

---

## 6. 종합 평가

| 항목 | 등급 | 코멘트 |
|------|------|--------|
| 아키텍처 | A- | 깔끔한 분리, Protocol 설계. str/Path 혼재가 미미한 감점 |
| 정확성 | B+ | 핵심 로직은 정상. 에러 처리(C4, C5)와 무시되는 실패(I7)가 아쉬움 |
| 보안 | B+ | dangerous_mode opt-in은 탁월. SafetyFilter 범위는 좁음 |
| 테스트성 | B | 테스트는 양호하나 `sys.exit` in `__init__`이 에러 경로 테스트를 막음 |
| 문서 | A | README, AGENTS.md 모두 충실. 커밋 형식 불일치가 유일한 문제 |
| Git 관리 | A | 12개 커밋, 일관된 형식, phase 태그. Phase 3 태그 매핑만 약간 불명확 |

### 최종 판결

> **코드베이스는 잘 설계되었고 기능적으로 정상 동작합니다.** 하지만 Critical Issues 5개를 해결하지 않으면 프로덕션 사용은 권장되지 않습니다.
>
> **가장 중요한 5가지:**
> 1. `__init__`의 `sys.exit()` → 예외로 변경
> 2. `harness.json` guardrail override 버그 수정
> 3. `smoke_backends.py`의 ollama/lmstudio dead code 제거
> 4. 백엔드 `invoke()` 예외 처리 추가
> 5. `GitManager.commit_all` return code 검사
>
> 이 5개를 해결하면 프로젝트는 "완성" 상태로 판단할 수 있습니다.

---

*본 리뷰는 전체 코드베이스를 정적 분석하여 작성되었습니다.*
