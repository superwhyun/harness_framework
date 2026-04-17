# Claude Supplement

이 저장소의 canonical 프로젝트 지침은 `AGENTS.md` 이다.

Claude Code에서는 아래 순서로 사용한다.

1. `AGENTS.md`
2. `docs/HARNESS.md`
3. 필요하면 `.claude/commands/harness.md`, `.claude/commands/review.md`

프로젝트 명령:

- `/harness`
- `/review`

배치 실행기 `scripts/execute.py` 는 선택 사항이다.
기본 사용 방식은 Claude Code가 이 저장소의 문서를 읽고 인터랙티브하게 작업하는 것이다.
