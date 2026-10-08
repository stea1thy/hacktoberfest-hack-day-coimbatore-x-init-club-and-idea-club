# P2 kickoff prompt — Telemetry, verification, hogs, UI

> Paste everything below the line into your agent as the first message.

---

Read `AGENTS.md` and `PCSENSE.md` fully (especially §4.4, §4.5, §4.10, §5, §9, §17). I am **P2**. I own: `pcsense/telemetry/**`, `pcsense/verify/**`, `tools/hog_mem.py`, `tools/hog_io.py`, `app.py`, `pcsense/ui/**`. Do not edit anything else. `pcsense/contracts.py` is frozen (owned by P1).

Before writing code, give me a short plan: files you'll create and tests you'll write. Wait for my go-ahead. Then work in the order below, one task at a time, committing after each.

## Phase A — start immediately (no dependency on contracts.py)

**A1. `tools/hog_mem.py`** — demo memory hog.
- Args: `--gb` (float, default 3), `--hold` seconds (default 600). Allocate a `bytearray` and **touch every page** (write one byte per 4096) so memory is really committed, not just reserved. Print PID. Exit cleanly on Ctrl+C. Release memory on exit.

**A2. `tools/hog_io.py`** — demo disk-I/O hog.
- Args: `--mb` (default 512), `--seconds` (default 600), `--threads` (default 4). Work only inside a temp dir under `%TEMP%\pcsense_hog_io`; delete it on exit. Loop: write chunks, `os.fsync`, read back at random offsets, from several threads. Print PID.
- A fast NVMe may not reach 100% disk time. Verify with `typeperf` (A3) and raise threads/chunk size if needed. Report what you actually measured.

**A3. `pcsense/telemetry/collectors.py`** — all real measurement, no LLM.
- CPU: `psutil.cpu_percent` over a short interval. RAM and swap via `virtual_memory` / `swap_memory`. Disk free/total of the system drive via `shutil.disk_usage(os.environ.get("SystemDrive","C:")+"\\")`.
- Per-process: `psutil.process_iter`. `cpu_percent` needs priming (call, sleep ~0.5–1 s, call again). Handle `AccessDenied`/`NoSuchProcess` by skipping. Memory in GB from `memory_info().rss`.
- **Per-process I/O is cumulative**: read `io_counters()` twice ~2 s apart and compute MB/s from the delta.
- For Python processes show a useful display name such as `python.exe [hog_mem.py]` (take the script name from `cmdline()`), since "python.exe" alone is ambiguous.
- Disk active %: run `typeperf` via `subprocess.run([...list...], shell=False, timeout=5)` with **fixed arguments only** (`\PhysicalDisk(_Total)\% Disk Time`, one sample). Parse the CSV output. Counter names are localized on non-English Windows — if parsing fails, return `None` (diagnosis rules must skip conditions whose input is `None`). No other subprocess is allowed.
- `collect_evidence() -> Evidence` per `contracts.py`. Test that numbers roughly match Task Manager while hogs run.

**A4. `pcsense/telemetry/health.py` and `diagnosis.py`** — copy rules from PCSENSE.md §4.4 and §4.5 as **data tables** (list of dicts), not scattered `if`s.
- `health_score(evidence) -> (score, breakdown[list of (reason, penalty)])`.
- `diagnose(evidence) -> list[Hypothesis]` sorted by confidence; each hypothesis lists satisfied and unsatisfied conditions with the evidence values (the UI will display them). Confidence = sum of weights of true conditions. Never use an LLM here.
- Tests: feed synthetic Evidence for memory pressure, I/O saturation, CPU bound, healthy, and missing-values cases.

## Phase B — after I tell you P1's skeleton is pulled

**B1. `pcsense/verify/verify.py`**
- `before()` / `after()` capture a measurement dict: RAM% and CPU% as the **median of 5 samples over ~5 s**, disk active %, drive free GB, and sandbox directory bytes when relevant. Remember the model is already resident in RAM; do not attribute its memory to the fix.
- `compare(before, after, scenario) -> VerifyResult` with scenarios `memory_hog`, `io_hog`, `storage_cleanup`. "Improved" requires a real measured change (e.g. RAM down ≥ 5 points AND target PID gone; sandbox bytes down by roughly the expected amount). If not improved, the summary must say plainly: **"The attempted fix did not resolve the issue."** Never hard-code numbers outside tests.
- For storage report **reclaimable** (quarantined) and **recovered** (after emptying) separately. Primary metric is sandbox bytes, secondary is drive free space (noisy).

**B2. Streamlit UI (`app.py`, `pcsense/ui/**`)** — starts after telemetry works (~13:00). Build against **mock events** first.
- Layout: top metric row (CPU, RAM, disk free, health score with a "why" expander showing deductions), request text box, **live agent activity feed**, plan view, before/after panel, tabs for Audit log (reads SQLite) and Eval results (reads `eval/results/latest.md` if present).
- Sidebar: autonomy selector (Observe / Ask / Auto-low-risk; default Ask), model name (read from env), sandbox path, cached-mode indicator.
- Plan view: each action with risk badge (LOW/MEDIUM/HIGH), size, rationale, a checkbox, plus a **"Not touching"** section listing `plan.excluded` items with reasons. Approve / Deny buttons. Separate confirmation buttons for **Stop process** and **Empty quarantine** (always required).
- **Streamlit reruns the script on every click and cannot pause a generator waiting for a button.** So the orchestrator API is two-phase: `orchestrator.start(request, autonomy) -> Iterator[Event]` ending with a `plan` event, then `orchestrator.execute(plan, approved_ids) -> Iterator[Event]`. Store the plan in `st.session_state`. P1 owns the final API; adapt to it and tell me if it differs from this.
- Show events as concise one-line steps with evidence. **Never display raw model reasoning.** Show filenames/process names as plain escaped text.

## Rules for you
- No `shell=True`; no model- or user-influenced subprocess arguments; no deleting anything outside `safety/`.
- Never run `hog_*` scripts in a way you can't stop; always print PID and support Ctrl+C.
- Don't change `Evidence`/`Process` fields. If you need one, stop and tell me (P1 decides).
- Tests for every module. Don't weaken tests. Report honestly what you didn't test.

## Checkpoints
12:30 hogs + collectors working · 13:15 diagnosis correct on live hogs · 14:00 verify works against real before/after · 14:45 UI feature freeze.
