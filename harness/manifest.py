from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

_TZ = timezone(timedelta(hours=9))


def _stamp() -> str:
    return datetime.now(_TZ).strftime("%Y-%m-%dT%H:%M:%S%z")


def _empty_manifest(project: str) -> dict:
    return {
        "schema_version": 1,
        "project": project,
        "updated_at": None,
        "modules": [],
        "routes": [],
        "shared_contracts": [],
        "integration_points": [],
        "known_issues": [],
        "phase_history": [],
    }


def update_project_manifest(phases_dir: Path, phase_dir_name: str, baseline: dict) -> None:
    manifest_path = phases_dir / "project-manifest.json"

    if manifest_path.exists():
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            manifest = _empty_manifest(baseline.get("project", "unknown"))
    else:
        manifest = _empty_manifest(baseline.get("project", "unknown"))

    # Modules — update by name (last phase wins)
    modules_by_name = {
        m["name"]: m
        for m in manifest.get("modules", [])
        if isinstance(m, dict) and m.get("name")
    }
    for module in baseline.get("modules", []):
        if not isinstance(module, dict) or not module.get("name"):
            continue
        modules_by_name[module["name"]] = {
            "name": module["name"],
            "purpose": module.get("purpose", ""),
            "phase": phase_dir_name,
            "owned_paths": module.get("owned_paths", []),
            "contracts": module.get("contracts", []),
        }
    manifest["modules"] = list(modules_by_name.values())

    # Routes — dedup by method+path
    routes_seen = {(r.get("method"), r.get("path")) for r in manifest.get("routes", [])}
    for route in baseline.get("routes", []):
        if not isinstance(route, dict):
            continue
        key = (route.get("method"), route.get("path"))
        if key not in routes_seen:
            manifest["routes"].append({**route, "phase": phase_dir_name})
            routes_seen.add(key)

    # Shared contracts — dedup by path
    contracts_seen: set[str] = set()
    for c in manifest.get("shared_contracts", []):
        p = c.get("path") if isinstance(c, dict) else c
        if p:
            contracts_seen.add(p)
    for contract in baseline.get("shared_contracts", []):
        if isinstance(contract, str):
            if contract not in contracts_seen:
                manifest["shared_contracts"].append({"path": contract, "purpose": "", "phase": phase_dir_name})
                contracts_seen.add(contract)
        elif isinstance(contract, dict) and contract.get("path"):
            if contract["path"] not in contracts_seen:
                manifest["shared_contracts"].append({**contract, "phase": phase_dir_name})
                contracts_seen.add(contract["path"])

    # Integration points — dedup by name
    ips_seen = {ip.get("name") for ip in manifest.get("integration_points", []) if isinstance(ip, dict)}
    for ip in baseline.get("integration_points", []):
        if not isinstance(ip, dict) or not ip.get("name"):
            continue
        if ip["name"] not in ips_seen:
            manifest["integration_points"].append({**ip, "phase": phase_dir_name})
            ips_seen.add(ip["name"])

    # Known issues — append with phase tag
    for issue in baseline.get("known_issues", []):
        if isinstance(issue, dict):
            manifest["known_issues"].append({**issue, "phase": phase_dir_name})
        elif isinstance(issue, str):
            manifest["known_issues"].append({"description": issue, "phase": phase_dir_name})

    manifest.setdefault("phase_history", []).append({
        "phase": phase_dir_name,
        "tag": baseline.get("tag", ""),
        "completed_at": baseline.get("completed_at", ""),
    })
    manifest["updated_at"] = _stamp()

    manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
