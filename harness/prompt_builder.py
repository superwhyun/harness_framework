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
    def load_project_manifest(phases_dir: Path) -> str:
        manifest_path = phases_dir / "project-manifest.json"
        if not manifest_path.exists():
            return ""
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return ""

        lines = ["## 프로젝트 현황 (project-manifest.json)", ""]

        modules = [m for m in manifest.get("modules", []) if isinstance(m, dict)]
        if modules:
            lines.append("### 모듈")
            for m in modules:
                purpose = f" — {m['purpose']}" if m.get("purpose") else ""
                lines.append(f"- `{m['name']}`{purpose}")
                contracts = [c for c in m.get("contracts", []) if isinstance(c, str)]
                if contracts:
                    lines.append(f"  - contracts: {', '.join(contracts)}")

        routes = [r for r in manifest.get("routes", []) if isinstance(r, dict)]
        if routes:
            lines.append("")
            lines.append("### 라우트")
            for r in routes:
                purpose = f" — {r['purpose']}" if r.get("purpose") else ""
                lines.append(f"- {r.get('method', '?')} {r.get('path', '?')}{purpose}")

        shared = manifest.get("shared_contracts", [])
        if shared:
            lines.append("")
            lines.append("### 공유 계약")
            for c in shared:
                if isinstance(c, dict):
                    purpose = f" — {c['purpose']}" if c.get("purpose") else ""
                    lines.append(f"- `{c.get('path', '?')}`{purpose}")
                elif isinstance(c, str):
                    lines.append(f"- `{c}`")

        ips = [ip for ip in manifest.get("integration_points", []) if isinstance(ip, dict)]
        if ips:
            lines.append("")
            lines.append("### 통합 지점")
            for ip in ips:
                purpose = f" — {ip['purpose']}" if ip.get("purpose") else ""
                lines.append(f"- `{ip.get('name', '?')}` ({ip.get('type', '?')}){purpose}")

        if len(lines) <= 2:
            return ""
        return "\n".join(lines) + "\n\n"

    @staticmethod
    def build_step_context(index: dict) -> str:
        lines = [
            f"- Step {s['step']} ({s['name']}): {s['summary']}"
            for s in index["steps"]
            if s["status"] == "completed" and s.get("summary")
        ]
        if not lines:
            return ""
        return (
            "## 이전 Step 상태 요약\n\n"
            "이 요약은 진행 상태 확인용이다. 후속 개발 입력은 이전 구현 파일이 아니라 "
            "`module-map.json`, baseline artifact, public contract를 우선한다.\n\n"
            + "\n".join(lines)
            + "\n\n"
        )

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
                    if prev_output.get("next_actions"):
                        lines.append(f"- next_actions: {prev_output['next_actions']}")
                    lines.append("- note: 이전 step output은 복구용이다. 구현 입력은 public contract와 baseline을 우선한다.")
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
        manifest_context: str,
        step_context: str,
        resume_context: str,
        prev_error: Optional[str],
        feat_msg_template: str,
    ) -> str:
        commit_example = feat_msg_template.format(project=project, num="N", name="<step-name>")
        retry_section = f"\n## ⚠ 이전 시도 실패\n\n{prev_error}\n\n---\n\n" if prev_error else ""
        return (
            f"당신은 {project} 프로젝트의 개발자입니다. 아래 step을 수행하세요.\n"
            f"현재 실행 백엔드: {backend_name}\n\n"
            f"{guardrails}\n\n---\n\n"
            f"{manifest_context}"
            f"{step_context}{resume_context}{retry_section}"
            "## 작업 규칙\n\n"
            "1. 이 스텝에 명시된 작업만 수행하라.\n"
            f"2. phases/project-manifest.json이 있으면 전체 프로젝트 현황을 먼저 파악하고, 기존 모듈·계약과 충돌하지 않게 설계하라.\n"
            f"3. /phases/{phase_dir_name}/module-map.json이 있으면 모듈 소유권과 public contract를 먼저 따른다.\n"
            "4. 이전 step의 구현 내부는 기본 입력으로 삼지 말고, AC 달성에 필요한 경우에만 targeted read 하라.\n"
            "5. owned_paths 밖 수정이나 contract 변경이 필요하면 현재 step을 blocked로 기록하고 blocking-fix/contract-change step을 append하라.\n"
            f"6. /phases/{phase_dir_name}/index.json의 해당 step status를 업데이트하라.\n"
            "7. 모든 변경사항을 커밋하라:\n"
            f"   {commit_example}\n\n---\n\n"
        )
