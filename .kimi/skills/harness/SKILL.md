---
name: harness
description: Continue work in this repository using the canonical harness workflow and phase files.
---

Read these files first:

- `AGENTS.md`
- `docs/HARNESS.md`
- `docs/PRD.md`
- `docs/ARCHITECTURE.md`
- `docs/ADR.md`

Then inspect the current `phases/` state.

Target project resolution:

1. Use a project path appended by the user when present.
2. Otherwise read `.harness/current_project`.
3. If neither exists or the value is empty, ask the user for the target project path.

Rules:

1. Continue from the first `pending` step in the active phase of the target project.
2. Only work on one step at a time.
3. Do not invent missing context from previous conversations.
4. Use `module-map.json`, `phases/baselines/{phase-dir}.json`, and public contracts as the primary inputs for each step.

If the user appended extra instructions after `/skill:harness`, apply them as additional constraints.
