---
name: review
description: Review current changes in this repository using the canonical review workflow.
---

Read these files first:

- `AGENTS.md`
- `docs/REVIEW.md`
- `docs/ARCHITECTURE.md`
- `docs/ADR.md`

Then inspect the current diff and produce a findings-first review.

Rules:

1. Focus on bugs, regressions, risky assumptions, and missing verification.
2. Point to concrete files and locations when possible.
3. If no issues are found, state that explicitly.
4. Keep the review aligned with the current phase/step and any existing handoff files.

If the user appended extra instructions after `/skill:review`, apply them as additional review scope.
