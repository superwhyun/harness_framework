#!/usr/bin/env python3
"""
Scaffold a new module entry under docs/modules/ and update registry.json.
"""

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from harness.project_context import resolve_project_root
from scripts.phase_utils import load_template, render_template, read_json_file, write_json_file


def scaffold_module(
    root: Path,
    module_id: str,
    persona_name: str,
    parent_id: str,
    *,
    template_root: Path | None = None,
    force: bool = False,
):
    tpl_root = template_root or ROOT
    docs_modules = root / "docs" / "modules"
    module_dir = docs_modules / Path(module_id)
    module_dir.mkdir(parents=True, exist_ok=True)

    module_doc_path = module_dir / "MODULE.md"
    if force or not module_doc_path.exists():
        template = load_template(tpl_root, "MODULE.md.tmpl")
        rendered = render_template(template, {
            "module_id": module_id,
            "parent_id": parent_id or "없음",
            "persona_name": persona_name,
        })
        module_doc_path.write_text(rendered, encoding="utf-8")
        print(f"  created {module_doc_path.relative_to(root)}")
    else:
        print(f"  skipped {module_doc_path.relative_to(root)} (already exists, use --force to overwrite)")

    registry_path = docs_modules / "registry.json"
    registry, error = read_json_file(registry_path)
    if registry is None:
        registry_template = load_template(tpl_root, "registry.json.tmpl")
        rendered_registry = render_template(registry_template, {
            "project": root.name,
            "first_module_id": module_id,
            "first_persona_name": persona_name,
        })
        registry = json.loads(rendered_registry)
        registry["modules"][module_id]["module_doc"] = f"docs/modules/{module_id}/MODULE.md"
        if parent_id:
            registry["modules"][module_id]["parent"] = parent_id
    else:
        if module_id not in registry["modules"] or force:
            registry.setdefault("modules", {})[module_id] = {
                "persona": persona_name,
                "version": "1.0.0",
                "status": "planned",
                "children": [],
                "module_doc": f"docs/modules/{module_id}/MODULE.md",
            }
            if parent_id:
                registry["modules"][module_id]["parent"] = parent_id

        if parent_id and parent_id in registry["modules"]:
            parent_children = registry["modules"][parent_id].setdefault("children", [])
            if module_id not in parent_children:
                parent_children.append(module_id)

    registry["updated_at"] = datetime.now(timezone.utc).isoformat()
    write_json_file(registry_path, registry)
    print(f"  updated {registry_path.relative_to(root)}")


def main():
    parser = argparse.ArgumentParser(description="Scaffold a new module under docs/modules/")
    parser.add_argument("module_id", help="Module ID using slash path (e.g. auth/token)")
    parser.add_argument("--persona", required=True, help="Persona name (e.g. 'Token Manager')")
    parser.add_argument("--parent", default="", help="Parent module ID (e.g. auth)")
    parser.add_argument("--force", action="store_true", help="Overwrite existing MODULE.md")
    parser.add_argument("--root", help="Target project root; defaults to .harness/current_project")
    parser.add_argument("--template-root", help="Template root; defaults to harness framework root")
    args = parser.parse_args()

    try:
        root = resolve_project_root(ROOT, args.root, interactive=True)
    except RuntimeError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(1)

    template_root = Path(args.template_root).resolve() if args.template_root else ROOT

    scaffold_module(
        root,
        args.module_id,
        args.persona,
        args.parent,
        template_root=template_root,
        force=args.force,
    )
    print(f"Scaffolded module {args.module_id}")


if __name__ == "__main__":
    main()
