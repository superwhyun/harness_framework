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

Rules:

1. Continue from the first `pending` step in the active phase.
2. Only work on one step at a time.
3. Do not invent missing context from previous conversations.
4. Use `stepN-output.json` as the handoff source of truth when present.
5. Before ending the session, leave a structured handoff including `summary`, `files_changed`, `verification`, `known_issues`, `next_actions`, and `resume_hint`.

If the user appended extra instructions after `/skill:harness`, apply them as additional constraints.
