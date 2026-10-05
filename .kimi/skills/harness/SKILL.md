---
name: harness
description: Plan, develop and resume scoped coding units in the current session using one task record.
---

Apply the user's request in the current session with already-loaded target project rules.
Small changes need no scaffold. For substantial work use an existing plan or tasks/{task}.md
with goal/design and each unit's scope, acceptance criteria, dependencies, checks and status.
Implement and verify one ready unit, commit its changes and progress record, then proceed.
Group small steps that cannot work independently. At phase end verify integration and commit only additional changes.
Include only the current work, respecting target policy and explicit user instructions. Push and tags require a separate request.
Do not put the whole feature into one implementation unit or launch another model CLI/session.
Optional scripts/scaffold_task.py only creates a document. Read docs/HARNESS.md only when needed.
Resume existing task or phase records without overwriting history. Record verification and next action before handoff.
Repeat passed checks only after relevant changes or new concerns. Do not limit execution to one unit per session.
Prefer the user's target path. Consult .harness/current_project only when selecting another project here.
