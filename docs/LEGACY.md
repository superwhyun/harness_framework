# Legacy phase tools

기존 phase 프로젝트를 재개하거나 명시적으로 배치 실행할 때 사용하는 호환 도구다.
새 작업은 `tasks/{task}.md`를 권장한다. 기존 `phases/` 이력과 step 번호는 보존한다.

```bash
python3 scripts/use_project.py /path/to/repo
python3 scripts/scaffold_phase.py 8-feature --project my-app --steps setup feature --root /path/to/repo
python3 scripts/validate_phase.py 8-feature --root /path/to/repo
python3 scripts/execute.py 8-feature --backend claude --root /path/to/repo
python3 scripts/smoke_backends.py
```

scaffold는 기존 phase를 덮어쓰지 않는다. 검증기는 schema 1/2를 지원하며 schema 2는 module-map을 요구한다.
모듈 도구와 템플릿은 기존 구조를 유지하는 프로젝트에만 사용한다.

## 실행과 완료

실행기는 준비된 pending step을 선택한다. `depends_on`이 있으면 선행 step 완료를 기다리고,
실행 가능한 `blocking-fix`를 우선한다. 의존 관계가 없으면 기존 index 순서를 사용한다.
`phases/STOP`이 있으면 다음 모델 호출·검사 전에 중단한다. 실행 중인 호출을 즉시 멈추려면 Ctrl-C를 사용한다.

새로 실행하는 step의 완료 조건은 다음과 같다.

- 백엔드 정상 종료와 현재 step의 `completed`, 비어 있지 않은 `summary`.
- `checks`가 있으면 실행기가 대상 저장소에서 직접 수행하고 전부 통과해야 한다.
- `checks`가 없으면 에이전트가 `verification.status: passed`와 `verification.details`에 검증 근거를 기록한다.

```json
{
  "step": 1,
  "name": "feature",
  "status": "pending",
  "depends_on": [0],
  "checks": [["python3", "-m", "unittest", "discover", "-s", "tests"]]
}
```

`checks`는 셸 문자열이 아닌 argv 배열의 목록이다. 파이프 등이 필요하면 저장소의 검증 스크립트를 지정한다.
검사는 사용자가 선택한 프로젝트 명령이며 모델의 tool sandbox 밖에서 실행된다. 실제 프로젝트에 맞는 명령을 설정한다.
에이전트가 실행 중 checks·depends_on을 약화하거나 다른 step을 대신 완료 처리하면 중단한다.
검사 명령은 실행 전에 준비한다. 수동 확인이 필요한 AC는 실제 관찰과 한계를 `verification.details`에 남긴다.
자체 기록은 독립 검증과 다르며, checks도 그 명령이 검사하는 범위만 보장한다.
기존 완료 step에는 새 필드를 소급 요구하지 않는다.

모든 step이 완료돼야 baseline·manifest·상위 index를 갱신한다. 기존 baseline은 보존하고 재개 시 manifest를 중복 누적하지 않는다.
손상된 JSON을 빈 기록으로 대체하지 않으며 새 상태 JSON은 원자적으로 저장한다.

## 실패와 재개

인증·설정 오류, timeout, 에이전트의 error/blocked, 진전 없는 실패는 중단한다.
일시적 서비스 오류 또는 코드 변경 진전이 있는 실패만 `execution.max_attempts` 상한 안에서 재시도한다.
기본 상한은 3회이며 의무적으로 3회를 소모하지 않는다. 일시적 오류에는 짧은 backoff를 적용한다.
각 시도의 종료 코드·소요 시간과 실패 원인을 index에 기록한다. timeout·Ctrl-C는 POSIX에서 자식 프로세스 그룹도 종료한다.

실패 후 원인과 기존 변경을 확인하고 해당 step을 `pending`으로 되돌려 재개한다.
Git 커밋 실패 시에는 통과한 step을 다시 실행할 필요 없이 Git 문제를 해결한 뒤 재개한다.

```bash
python3 scripts/execute.py 8-feature --root /path/to/repo --no-commit
```

기본 모드는 최초 커밋이 있는 깨끗한 Git 저장소에서 시작하여 branch와 커밋을 관리한다.
`--no-commit`은 현재 branch와 미커밋 변경을 유지하며 자동 커밋·push를 끈다.
작업 중에는 같은 저장소에서 다른 작성자가 변경하지 않도록 별도 checkout을 사용하거나 `--no-commit`을 선택한다.
`--push`는 명시한 경우에만 실행하며 실패를 오류로 보고한다. `--no-commit`과 함께 사용할 수 없다.
Git 추적 대상인 phase 완료 메타데이터도 최종 커밋에 포함한다. `.gitignore`는 존중하며 자동 태그는 만들지 않는다.

## 백엔드 설정

`harness.json`은 배치 기능에만 필요하다. 최소 설정은 `default_backend`이며 모델은 각 CLI 설정을 사용한다.
기본 Claude는 `acceptEdits`, Codex는 `workspace-write`로 파일 편집을 허용한다. 셸·네트워크 등 추가 권한은 도구 설정을 따른다.
권한을 자동 우회하지 않는다. 기존 `dangerous_mode`는 격리된 환경에서 명시적으로 선택할 때만 유지되는 호환 옵션이다.

```json
{
  "default_backend": "codex",
  "execution": {"max_attempts": 3, "timeout_seconds": 1800},
  "backends": {
    "codex": {
      "command": ["codex", "exec", "--json", "--sandbox", "workspace-write", "--model", "YOUR_MODEL_ID", "{prompt}"],
      "instruction_mode": "native"
    }
  }
}
```

`YOUR_MODEL_ID`는 해당 CLI·계정이 제공하는 모델 ID로 바꾼다. 모델·추론 설정을 하네스가 자동 변경하지 않는다.
기본 CLI는 `native` 방식으로 이미 로딩된 규칙을 재주입하지 않고, 빠진 대상 규칙만 읽도록 안내한다.
사용자 정의 command는 `inline`이 기본이다. 자체 규칙 로더가 있으면 `instruction_mode: native`를 명시한다.
`guardrail_files`로 대상 저장소의 추가 규칙 파일을 지정할 수 있다. 프레임워크 개발 규칙은 외부 프로젝트에 주입하지 않는다.
전체 manifest·과거 요약은 반복 주입하지 않는다. 명시적 의존 step 요약과 원본 기록 경로를 제공한다.

`SafetyFilter`는 이전 코드 호환을 위해 남아 있으나 모델 호출 경로에서는 사용하지 않는다.
자연어 프롬프트를 명령으로 차단하지 않으며, 실제 도구 권한은 백엔드에서 관리한다.

스모크 검사는 실행 가능한 CLI의 help만 확인한다. 미설치 CLI는 skip, 명시적 `--backend`가 실행 불가하면 실패한다.
모델 호출·로그인·실제 코드 변경을 검증하는 검사는 아니다.
공식 Codex 비대화형 실행 규약: https://learn.chatgpt.com/docs/non-interactive-mode
