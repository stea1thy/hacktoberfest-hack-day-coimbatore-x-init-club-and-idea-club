# PCSense — Shared Rules for ALL coding agents (Claude Code, Antigravity, others)

PCSense is a local-first AI technician for Windows 11. Gemma 4 (via Ollama) routes intent, picks read-only tools and explains evidence. **Deterministic code** does diagnosis rules, policy, execution and verification.

**Source of truth: `PCSENSE.md` (read it fully before your first change).** If anything here conflicts with it, `PCSENSE.md` §17 (ownership) and this file win; otherwise ask the human.

## 1. Scope — three flows only
1. "Why is my PC slow?" → diagnose → propose → approve → act → verify
2. "Free up N GB" → scan → plan → approve → quarantine → empty (approve) → verify
3. Audit log + prompt-injection moment
Do NOT build roadmap items (drivers, registry, startup changes, GPU, anomaly ML, Electron, restore points, shell tools). Stretch items (PCSENSE.md §3.2) only if the human says so.

## 2. Ownership (edit ONLY your own paths; ask the human before touching others)
| Owner | Paths |
|---|---|
| P1 | `pcsense/contracts.py`, `pcsense/safety/**`, `pcsense/orchestrator.py`, `tests/safety/**`, `Makefile`, `LICENSE`, root config |
| P2 | `pcsense/telemetry/**`, `pcsense/verify/**`, `tools/hog_mem.py`, `tools/hog_io.py`, `app.py`, `pcsense/ui/**` |
| P3 | `pcsense/storage/**`, `tools/make_sandbox.py`, `tests/storage/**`, `README.md`, `docs/**` |
| P4 | `pcsense/agent/**`, `eval/**`, `tests/agent/**` |

`pcsense/contracts.py` is **frozen** after the skeleton commit. Need a change? Stop and tell the human; P1 decides. Never "fix" another owner's module — report the problem.

## 3. Hard safety rules (non-negotiable)
- **No `shell=True`. No subprocess argument may contain model-influenced or user-typed text.** The only allowed subprocess is `typeperf` with fixed arguments.
- **No tool that executes arbitrary commands, PowerShell, or registry edits.** Ever.
- All write/delete actions go through `safety/policy.py` → `safety/executor.py`. Never call `os.remove`, `shutil.rmtree`, `Path.unlink` etc. on a path outside `safety/quarantine.py` / `safety/executor.py`.
- Write actions are allowed **only inside the sandbox root** (`PCSENSE_SANDBOX`) and only if that root contains the marker file `.pcsense_sandbox` (created by `tools/make_sandbox.py`). No marker → refuse. Real folders are read-only analysis.
- Scanners use `follow_symlinks=False`; reject symlinks, junctions and reparse points (`st_file_attributes & FILE_ATTRIBUTE_REPARSE_POINT`). Normalize with `realpath` + `normcase` before comparing paths.
- Filenames, process names and log text are **untrusted data**. In prompts they appear only inside a delimited data field; never as instructions.
- **While developing, never run delete/quarantine/stop-process code against real folders or real processes.** Test only against the generated sandbox and the hog scripts. Do not run destructive terminal commands without the human reviewing them.
- Approvals are bound to a hash of the exact action list (`plan_hash`). Executor refuses on mismatch.
- `stop_process` and `empty_quarantine` always require confirmation at every autonomy level.

## 4. Gemma / Ollama rules (owner: P4)
- Use Ollama's JSON-schema `format` (schema-constrained output). **Do not use native tool calling** unless the human enables `PCSENSE_TOOL_MODE=native`.
- Always `think: false`, `temperature: 0`, `num_ctx: 4096`, `keep_alive: 30m`, short outputs.
- Model name comes from env `PCSENSE_MODEL` (default `gemma4:e2b`). Never hard-code it.
- Invalid JSON → one retry → deterministic playbook fallback. Never loop unbounded (max 4 tool steps, no repeated identical calls).
- Gemma can only choose from tools/actions the code offers. Confidence and health scores come from rule tables, never from the LLM.
- Every number in LLM text must appear in the evidence (`agent/faithfulness.py`).

## 5. Code standards
- Python 3.11+, type hints, pydantic models from `contracts.py`, no global mutable state.
- Windows-first: use `pathlib`, handle access-denied (skip + count), never crash a scan.
- Keep functions small and testable. Rules/thresholds live in data tables, not buried in code.
- Every new module needs at least one test. Policy code needs adversarial tests (`..\` traversal, junction trap, protected paths/processes, case and 8.3 names, plan_hash mismatch).
- **Never weaken, skip or delete a test to make it pass.** Fix the code or ask the human.
- Never fake results, mock "success", or hard-code measured numbers outside tests. Verification must measure.
- Don't add dependencies without telling the human (update `requirements.txt` in the same commit).

## 6. Git workflow (hackathon rules: real, incremental commits from every teammate)
- Work on a branch named `p<N>/<topic>`; PR to `main`; merge without squashing; pull/rebase before starting each task.
- Conventional commits: `feat(storage): duplicate hashing pipeline`, `test(safety): junction trap`, `fix(agent): retry on invalid json`.
- Stage specific files only (no `git add -A`). Commit about every 45 minutes or after each working module.
- Never rewrite or backdate history. Commits are made under the human's own identity.
- Add the co-author trailer your tool uses if it adds one; do not remove it.

## 7. How to work with the human
- Start each task with a short plan: files you will create/change, tests you will write. Wait for a go-ahead on anything non-trivial.
- One module at a time. Run the tests and the relevant app path before saying "done".
- If a requirement is ambiguous or conflicts with these rules, ask — do not guess.
- Report honestly: what works, what doesn't, what you did not test.

## 8. Definition of done (per module)
Implements the signature in `contracts.py`/PCSENSE.md §8, has passing tests, handles errors without crashing, logs via `audit.log` where it acts, and returns real measured data (mock only until the real module lands).

## 9. Environment variables
`PCSENSE_MODEL` (default `gemma4:e2b`), `PCSENSE_TOOL_MODE` (`schema`|`native`), `PCSENSE_SANDBOX` (e.g. `C:\pcsense_sandbox`), `PCSENSE_CACHED` (`1` = replay recorded traces).
