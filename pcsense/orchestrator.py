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

from typing import Iterator

from pcsense.agent.explainer import explain
from pcsense.agent.loop import run_loop
from pcsense.agent.router import route
from pcsense.contracts import Action, Evidence, Event, Hypothesis, Plan, RouterOut
from pcsense.safety import audit, executor, policy
from pcsense.simulate import simulate_plan
from pcsense.storage.candidates import candidates
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
    router_out = route(request)

    yield Event(kind="step", payload={"tool": "run_loop", "args": router_out.model_dump()})
    evidence, tool_results = run_loop(router_out.intent, router_out.params)
    for tool_result in tool_results:
        audit.log("tool", tool_result)
        yield Event(kind="step", payload=tool_result)
    yield Event(kind="evidence", payload=evidence.model_dump())

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
    explanation = explain(evidence, hypotheses, actions)
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
    evidence_before = verify_before()
    for result in executor.run(plan, action_ids):
        yield Event(kind="action_result", payload=result.model_dump())
    evidence_after = verify_after()
    comparison = verify_compare(evidence_before, evidence_after)
    audit.log("verify", comparison.model_dump())
    yield Event(kind="verify", payload=comparison.model_dump())


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
