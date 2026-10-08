"""Single entry point the UI calls: ties router -> loop -> diagnosis -> explainer -> plan ->
approval -> policy -> executor -> verify together, emitting Events for the live activity feed
(PCSENSE.md §17, §4.1).

Owner: P1. Streamlit reruns the whole script per interaction, so this is split into two calls
instead of one that blocks mid-stream waiting for a button click:

  1. `run(request, autonomy)` — routes the request, gathers evidence, diagnoses, builds a
     Plan, and stops at an `approval_request` event for anything that isn't auto-executed.
     At autonomy >= 2, LOW-risk actions execute immediately (still logged) since §4.6 allows
     it; everything else (including anything the policy engine will flag HIGH, like
     stop_process/empty_quarantine) always waits for step 2 regardless of autonomy level.
  2. `execute_approved(plan, approved_ids)` — the continuation once a human clicks approve.
     The UI calls this with the `plan` and `action_ids` it got from the `approval_request`
     event. `executor.run()` re-validates everything against `policy.check()` and the
     plan_hash; approval here is a UI-level gate, not a bypass of either.
"""
from __future__ import annotations

import os
from typing import Iterator

from pcsense.agent.explainer import explain, template_explain
from pcsense.agent.loop import run_loop
from pcsense.agent.router import baseline_route, route
from pcsense.contracts import Action, Evidence, Event, Explanation, Hypothesis, Plan, RouterOut
from pcsense.safety import audit, executor, policy
from pcsense.simulate import simulate_plan
from pcsense.storage.candidates import candidates
from pcsense.telemetry.collectors import collect_evidence
from pcsense.telemetry.diagnosis import classify_hypotheses, diagnose
from pcsense.verify.verify import after as verify_after
from pcsense.verify.verify import before as verify_before
from pcsense.verify.verify import compare as verify_compare

# Intents with a diagnose -> plan -> approve -> act -> verify loop (AGENTS.md §1: three flows
# only). Everything else (status, explain_storage, what_changed, unsupported) just reports
# evidence and stops — no plan, no actions.
_ACTIONABLE_INTENTS = {"diagnose_slow", "free_space"}


def run(request: str, autonomy: int) -> Iterator[Event]:
    audit.log("request", {"text": request, "autonomy": autonomy})

    yield Event(kind="step", payload={"tool": "route", "args": {"text": request}})
    router_out = _route_with_fallback(request)

    evidence = collect_evidence()
    yield Event(kind="evidence", payload=evidence.model_dump())

    yield Event(kind="step", payload={"tool": "run_loop", "args": router_out.model_dump()})
    tool_results = _run_loop_safely(router_out.intent, router_out.params)
    for tool_result in tool_results:
        audit.log("tool", tool_result)
        yield Event(kind="step", payload=tool_result)

    if router_out.intent not in _ACTIONABLE_INTENTS:
        if router_out.intent == "unsupported":
            yield Event(kind="error", payload={"reason": "unsupported intent", "request": request})
        return

    hypotheses = diagnose(evidence)
    classification = classify_hypotheses(hypotheses, evidence)
    yield Event(
        kind="diagnosis",
        payload={
            "hypotheses": [h.model_dump() for h in hypotheses],
            "primary": classification["primary"].model_dump() if classification["primary"] else None,
            "secondary": [h.model_dump() for h in classification["secondary"]],
            "normal": classification["normal"],
        },
    )

    actions = _propose_actions(router_out, evidence, hypotheses)
    explanation = _explain_with_fallback(evidence, hypotheses, actions)
    yield Event(kind="diagnosis", payload={"explanation": explanation.model_dump()})

    if not actions:
        return

    plan = Plan(
        goal=request,
        hypotheses=[h.model_dump() for h in hypotheses],
        actions=actions,
        plan_hash=policy.compute_plan_hash(actions),
    )
    simulation = simulate_plan(evidence, actions)
    yield Event(kind="plan", payload={"plan": plan.model_dump(), "simulation": simulation})

    if autonomy == 0:
        return  # Observe: plan is shown, but Execute is disabled — no approval, no auto-run

    auto_ids = [a.id for a in actions if a.risk == "LOW"] if autonomy >= 2 else []
    manual_ids = [a.id for a in actions if a.id not in auto_ids]

    if auto_ids:
        yield from _execute_and_verify(plan, auto_ids)
    if manual_ids:
        yield Event(kind="approval_request", payload={"plan": plan.model_dump(), "action_ids": manual_ids})


def execute_approved(plan: Plan, approved_ids: list[str]) -> Iterator[Event]:
    """Continuation after a human approves `approved_ids` from a `plan` the UI is holding.
    `stop_process` and `empty_quarantine` must only ever run through this path (§4.6)."""
    yield from _execute_and_verify(plan, approved_ids)


def _execute_and_verify(plan: Plan, action_ids: list[str]) -> Iterator[Event]:
    if not action_ids:
        return
    actions_by_id = {a.id: a for a in plan.actions}
    approved_actions = [actions_by_id[aid] for aid in action_ids if aid in actions_by_id]
    scenario, target_pid, sandbox_dir, expected_freed_bytes = _infer_verify_scenario(approved_actions)

    evidence_before = verify_before(sandbox_dir=sandbox_dir, target_pid=target_pid)
    for result in executor.run(plan, action_ids):
        yield Event(kind="action_result", payload=result.model_dump())
    evidence_after = verify_after(sandbox_dir=sandbox_dir, target_pid=target_pid)
    comparison = verify_compare(evidence_before, evidence_after, scenario, expected_freed_bytes)
    audit.log("verify", comparison.model_dump())
    yield Event(kind="verify", payload=comparison.model_dump())


def _infer_verify_scenario(actions: list[Action]) -> tuple[str, int | None, str | None, int]:
    """verify.compare() needs to know WHAT it's verifying (memory_hog/io_hog/storage_cleanup)
    plus the specific target_pid/sandbox_dir/expected_freed_bytes for that scenario — none of
    which `Action` carries explicitly. Infers it from the approved actions themselves. Returns
    (scenario, target_pid, sandbox_dir, expected_freed_bytes)."""
    stop_actions = [a for a in actions if a.tool == "stop_process"]
    if stop_actions:
        target_pid = stop_actions[0].params.get("pid")
        # _propose_diagnose_actions() embeds the triggering hypothesis name verbatim in the
        # rationale (see below) — reuse that instead of threading a new field through Action.
        scenario = "io_hog" if "disk_io_saturation" in stop_actions[0].rationale else "memory_hog"
        return scenario, target_pid, None, 0

    storage_actions = [a for a in actions if a.tool in ("quarantine_paths", "empty_quarantine")]
    if storage_actions:
        sandbox_root = policy.get_sandbox_root()
        expected_freed_bytes = sum(a.est_bytes for a in storage_actions)
        return "storage_cleanup", None, str(sandbox_root) if sandbox_root else None, expected_freed_bytes

    return "memory_hog", None, None, 0


def _cached_mode() -> bool:
    """PCSENSE_CACHED=1 (AGENTS.md §9 / PCSENSE.md §11.3's documented demo safety net) skips
    live Ollama calls entirely — used by tests (never want 10s+ connection-refused delays per
    call) and as the real demo fallback if Ollama misbehaves."""
    return os.environ.get("PCSENSE_CACHED") == "1"


def _route_with_fallback(request: str) -> RouterOut:
    """agent/router.py's route() calls Ollama directly and raises on failure (no internal
    catch, unlike explain()/run_loop()) — fall back to their own baseline_route() keyword
    matcher rather than letting a down/missing Ollama take out the whole request."""
    if _cached_mode():
        return RouterOut(**baseline_route(request))
    try:
        router_dict = route(request)
    except Exception as exc:
        audit.log("tool", {"tool": "route", "error": str(exc), "fallback": "baseline_route"})
        router_dict = baseline_route(request)
    return RouterOut(**router_dict)


def _run_loop_safely(intent: str, params: dict) -> list[dict]:
    """agent/loop.py's run_loop() already catches its own Ollama failures internally and
    returns a plain list[dict] of tool-step events (no Evidence — that comes from
    collect_evidence() directly now). This guards against anything it doesn't catch."""
    try:
        return run_loop(intent, params)
    except Exception as exc:
        return [{"tool": "run_loop", "result": f"error: {exc}"}]


def _explain_with_fallback(evidence: Evidence, hypotheses: list[Hypothesis], actions: list[Action]) -> Explanation:
    """agent/explainer.py's explain() returns a plain dict (not an Explanation) and expects
    hypotheses as list[dict], not list[Hypothesis] — it calls h.get(...) internally, which
    would AttributeError on a pydantic object. Convert at the boundary both ways."""
    hypothesis_dicts = [h.model_dump() for h in hypotheses]
    if _cached_mode():
        return Explanation(**template_explain(evidence.model_dump(), hypothesis_dicts, actions))
    try:
        result = explain(evidence.model_dump(), hypothesis_dicts, actions)
        return Explanation(**result)
    except Exception:
        result = template_explain(evidence.model_dump(), hypothesis_dicts, actions)
        return Explanation(**result)


def _propose_actions(router_out: RouterOut, evidence: Evidence, hypotheses: list[Hypothesis]) -> list[Action]:
    if router_out.intent == "free_space":
        root = router_out.params.get("root")
        if not root:
            sandbox_root = policy.get_sandbox_root()
            root = str(sandbox_root) if sandbox_root else None
        if not root:
            return []
        return candidates(root, router_out.params.get("goal_gb"))
    if router_out.intent == "diagnose_slow":
        return _propose_diagnose_actions(evidence, hypotheses)
    return []


def _propose_diagnose_actions(evidence: Evidence, hypotheses: list[Hypothesis]) -> list[Action]:
    """Rule engine proposes; policy.check() decides what's actually allowed (e.g. it will
    correctly refuse to stop Ollama or PCSense's own process even if they top the list)."""
    if not hypotheses or not evidence.top_processes:
        return []
    top = hypotheses[0]
    if top.name not in ("memory_pressure", "cpu_bound", "disk_io_saturation"):
        return []
    rank_by = "mem_gb" if top.name == "memory_pressure" else "cpu_percent"
    culprit = max(evidence.top_processes, key=lambda p: getattr(p, rank_by))
    return [
        Action(
            id="a1",
            tool="stop_process",
            params={"pid": culprit.pid},
            risk="HIGH",
            rationale=(
                f"{culprit.name} (pid {culprit.pid}) is the top contributor to {top.name} "
                f"(confidence {top.confidence:.2f})."
            ),
        )
    ]
