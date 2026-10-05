from pathlib import Path
from typing import Optional


class PromptBuilder:
    @staticmethod
    def load_guardrails(root: Path, framework_root: Path, backend_guardrail_files: list[str],
                        instruction_mode: str = "inline") -> str:
        # Keep framework_root in the signature for existing callers, never inject its rules.
        paths = []
        seen = set()
        for name in ["AGENTS.md", *backend_guardrail_files]:
            path = root / name
            if path.is_file() and path.resolve() not in seen:
                seen.add(path.resolve())
                paths.append((name, path))
        if instruction_mode == "native":
            names = ", ".join(f"`{name}`" for name, _ in paths)
            return (
                "대상 프로젝트와 작업 경로의 지침을 따른다. 이미 자동 로딩된 지침은 다시 읽지 않는다.\n"
                + (f"{names} 중 로딩되지 않은 관련 지침만 확인한다.\n" if names else "")
            )
        return "\n\n".join(f"## 대상 규칙 ({name})\n\n{path.read_text(encoding='utf-8')}" for name, path in paths)

    @staticmethod
    def load_project_manifest(phases_dir: Path) -> str:
        if not (phases_dir / "project-manifest.json").is_file():
            return ""
        return (
            "프로젝트 현황 참조: `phases/project-manifest.json`. "
            "관련 모듈·공유 계약·통합 지점을 필요할 때 확인하고 실제 코드와 대조한다.\n\n"
        )

    @staticmethod
    def build_step_context(index: dict, current_step: Optional[dict] = None) -> str:
        steps = index["steps"]
        done = sum(s["status"] == "completed" for s in steps)
        lines = [f"진행: {done}/{len(steps)} 완료. 전체 이력은 이 phase의 index.json을 필요한 부분만 확인한다."]
        # Explicit dependencies, including transitive ones, are never dropped by a recency cap.
        by_id = {s["step"]: s for s in steps}
        pending = list((current_step or {}).get("depends_on", []))
        selected = set()
        while pending:
            step_id = pending.pop()
            if step_id in selected or step_id not in by_id:
                continue
            selected.add(step_id)
            pending.extend(by_id[step_id].get("depends_on", []))
        for step in steps:
            if step["step"] in selected:
                lines.append(f"- Step {step['step']} ({step['name']}, {step['status']}): {step.get('summary', '')}")
        return "\n".join(lines) + "\n\n"

    @staticmethod
    def build_preamble(
        project: str, phase_name: str, phase_dir_name: str, backend_name: str,
        guardrails: str, manifest_context: str, step_context: str,
        prev_error: Optional[str], feat_msg_template: str,
    ) -> str:
        retry = f"\n## 이전 시도\n{prev_error}\n기존 변경을 확인하고 원인을 해결한다. 완료한 작업을 반복하지 않는다.\n" if prev_error else ""
        return (
            f"{project} 프로젝트의 현재 step을 수행한다. 백엔드: {backend_name}.\n\n"
            f"{guardrails}\n{manifest_context}{step_context}{retry}\n"
            "## 작업과 완료\n"
            "- 필요한 코드·계약을 확인하고 변경 범위, 중요한 설계 선택, 검증 방법을 정한 뒤 구현한다.\n"
            "- 작은 연관 수정은 함께 처리한다. 사용자 목표 밖의 작업을 추가하지 않는다.\n"
            f"- 관련 경계가 필요하면 phases/{phase_dir_name}/module-map.json을 참고한다.\n"
            "- AC를 검증한다. index의 checks 명령은 실행기가 수행하므로 같은 검사를 의무적으로 중복 실행하지 않는다.\n"
            f"- phases/{phase_dir_name}/index.json의 현재 step에 summary와 상태를 기록한다. 다른 step을 대신 완료 처리하지 않는다.\n"
            '- checks가 없으면 verification: {"status": "passed", "details": "실행한 명령 또는 관찰, 결과와 범위"}를 기록한다.\n'
            "- 미실행·실패·외부 미확인을 통과로 기록하지 않는다. 실패는 error_message, 차단은 blocked_reason에 원인과 다음 행동을 남긴다.\n"
            "- 기존 step과 checks, depends_on은 보존한다. checks 변경이 필요하면 이유를 남기고 차단 상태로 종료한다.\n"
            "- Git 관리는 실행기 옵션에 따른다. 직접 커밋·태그·push하지 않는다.\n\n"
        )
