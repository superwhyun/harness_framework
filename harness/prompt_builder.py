import json
from pathlib import Path
from typing import Optional


class PromptBuilder:
    @staticmethod
    def load_guardrails(root: Path, framework_root: Path, backend_guardrail_files: list[str]) -> str:
        sections = []
        seen = set()

        def add_section(path: Path, title: str):
            if not path.exists() or not path.is_file():
                return
            resolved = path.resolve()
            if resolved in seen:
                return
            seen.add(resolved)
            sections.append(f"## {title}\n\n{path.read_text(encoding='utf-8')}")

        add_section(framework_root / "AGENTS.md", "하네스 프레임워크 규칙 (AGENTS.md)")
        framework_docs_dir = framework_root / "docs"
        if framework_docs_dir.is_dir():
            for doc in sorted(framework_docs_dir.glob("*.md")):
                add_section(doc, f"프레임워크 문서 ({doc.stem})")

        add_section(root / "AGENTS.md", "대상 프로젝트 규칙 (AGENTS.md)")
        docs_dir = root / "docs"
        if docs_dir.is_dir():
            for doc in sorted(docs_dir.glob("*.md")):
                add_section(doc, f"대상 프로젝트 문서 ({doc.stem})")

        for rel_path in backend_guardrail_files:
            project_path = root / rel_path
            framework_path = framework_root / rel_path
            add_section(project_path if project_path.exists() else framework_path, f"백엔드 보조 규칙 ({rel_path})")

        return "\n\n---\n\n".join(sections) if sections else ""

    @staticmethod
    def build_step_context(index: dict) -> str:
        lines = [
            f"- Step {s['step']} ({s['name']}): {s['summary']}"
            for s in index["steps"]
            if s["status"] == "completed" and s.get("summary")
        ]
        if not lines:
            return ""
        return "## 이전 Step 산출물\n\n" + "\n".join(lines) + "\n\n"

    @staticmethod
    def build_resume_context(phase_dir: Path, step_num: int) -> str:
        sections = []
        for prev_step in range(step_num - 1, -1, -1):
            out_path = phase_dir / f"step{prev_step}-output.json"
            if out_path.exists():
                try:
                    prev_output = json.loads(out_path.read_text(encoding="utf-8"))
                    lines = [f"## 이전 세션 handoff (Step {prev_step})", ""]
                    if prev_output.get("summary"):
                        lines.append(f"- summary: {prev_output['summary']}")
                    if prev_output.get("files_changed"):
                        lines.append(f"- files_changed: {', '.join(prev_output['files_changed'])}")
                    sections.append("\n".join(lines))
                    break
                except (json.JSONDecodeError, FileNotFoundError, PermissionError, OSError) as exc:
                    print(f"  WARN: resume context read failed for step {prev_step}: {exc}")
        return "\n\n".join(sections) + "\n\n" if sections else ""

    @staticmethod
    def build_preamble(
        project: str,
        phase_name: str,
        phase_dir_name: str,
        backend_name: str,
        guardrails: str,
        step_context: str,
        resume_context: str,
        prev_error: Optional[str],
        feat_msg_template: str,
    ) -> str:
        commit_example = feat_msg_template.format(phase=phase_name, num="N", name="<step-name>")
        retry_section = f"\n## ⚠ 이전 시도 실패\n\n{prev_error}\n\n---\n\n" if prev_error else ""
        return (
            f"당신은 {project} 프로젝트의 개발자입니다. 아래 step을 수행하세요.\n"
            f"현재 실행 백엔드: {backend_name}\n\n"
            f"{guardrails}\n\n---\n\n"
            f"{step_context}{resume_context}{retry_section}"
            "## 작업 규칙\n\n"
            "1. 이 스텝에 명시된 작업만 수행하라.\n"
            f"2. /phases/{phase_dir_name}/index.json의 해당 step status를 업데이트하라.\n"
            "3. 모든 변경사항을 커밋하라:\n"
            f"   {commit_example}\n\n---\n\n"
        )
