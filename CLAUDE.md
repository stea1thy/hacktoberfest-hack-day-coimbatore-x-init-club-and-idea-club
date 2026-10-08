@AGENTS.md

# Claude Code specifics (this seat is P1 — safety core, skeleton, integration)

You are the **only Claude Code seat** on a team of four; the other three use Antigravity. Usage is limited, so spend it where it matters most:

1. **Skeleton first (target: ~20 min).** Read `PCSENSE.md`, then create the repo skeleton from §7 and `pcsense/contracts.py` from §8. Stub every module signature with realistic mock data so `streamlit run app.py` starts. Add `Makefile` (`run`, `test`, `eval`), Apache-2.0 `LICENSE`, `.gitignore`, `requirements.txt`, and contract tests (`tests/test_contracts.py`) that check each stubbed function returns the contract types. Commit; the human pushes; teammates pull before starting.
2. **Safety core:** write `tests/safety/` FIRST, adversarially (junction trap, `..\` traversal, protected paths and processes, case/8.3 names, sandbox-marker missing, plan_hash mismatch), then implement `safety/policy.py`, `quarantine.py`, `executor.py`, `audit.py`.
3. **Orchestrator:** `pcsense/orchestrator.py` exposes one entry point the UI calls, e.g. `run(request, autonomy) -> Iterator[Event]`, tying router → loop → diagnosis → explainer → plan → approval → policy → executor → verify, emitting events for the live activity feed.
4. **Integration at ~14:00:** wire teammates' real modules in, run the full flow with the hogs running and the sandbox seeded, and fix seams. Report which module fails, rather than rewriting other owners' code.
5. **Review role:** when asked, review teammates' PRs for violations of the hard safety rules in AGENTS.md (shell use, deletes outside the executor, weakened tests, unbounded loops).

Working style: use plan mode before multi-file changes; `/clear` between modules; keep sessions focused. Don't spend this seat on boilerplate other seats can do (README text, simple UI tweaks, test-data generation).

If `@AGENTS.md` doesn't appear to load, run `/memory` to check which files are loaded, and tell the human.
