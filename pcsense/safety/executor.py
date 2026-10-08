"""Runs approved actions after policy.check() passes; refuses the whole batch on plan_hash
mismatch (§4.8-7) so the model cannot swap actions after the human approved them.

Owner: P1.
"""
from __future__ import annotations

import psutil

from pcsense.contracts import Action, ActionResult, Plan
from pcsense.safety import audit, policy, quarantine


def run(plan: Plan, approved_ids: list[str]) -> list[ActionResult]:
    results: list[ActionResult] = []

    recomputed_hash = policy.compute_plan_hash(plan.actions)
    if recomputed_hash != plan.plan_hash:
        for action_id in approved_ids:
            audit.log("denial", {"action_id": action_id, "reason": "plan_hash mismatch"})
            results.append(
                ActionResult(action_id=action_id, ok=False, detail="plan_hash mismatch — refusing execution")
            )
        return results

    actions_by_id = {a.id: a for a in plan.actions}
    for action_id in approved_ids:
        action = actions_by_id.get(action_id)
        if action is None:
            audit.log("denial", {"action_id": action_id, "reason": "unknown action id"})
            results.append(ActionResult(action_id=action_id, ok=False, detail="unknown action id"))
            continue

        decision = policy.check(action)
        audit.log("decision", {"action_id": action_id, "allowed": decision.allowed, "reason": decision.reason})
        if not decision.allowed:
            audit.log("denial", {"action_id": action_id, "reason": decision.reason})
            results.append(ActionResult(action_id=action_id, ok=False, detail=decision.reason))
            continue

        try:
            outcome = _dispatch(action)
            audit.log("result", {"action_id": action_id, "ok": True, **outcome})
            results.append(
                ActionResult(
                    action_id=action_id,
                    ok=True,
                    detail=outcome.get("detail", "ok"),
                    bytes_moved=outcome.get("bytes", 0),
                )
            )
        except Exception as exc:  # execution failure must not crash the batch
            audit.log("result", {"action_id": action_id, "ok": False, "error": str(exc)})
            results.append(ActionResult(action_id=action_id, ok=False, detail=f"execution error: {exc}"))

    return results


def stop_process(pid: int) -> dict:
    proc = psutil.Process(pid)
    proc.terminate()
    return {"detail": f"terminated pid {pid}", "bytes": 0}


def _dispatch(action: Action) -> dict:
    if action.tool == "quarantine_paths":
        paths = action.params["paths"]
        batch_id = action.params.get("batch_id", action.id)
        return quarantine.quarantine_paths(paths, batch_id)
    if action.tool == "empty_quarantine":
        return quarantine.empty_quarantine(action.params["batch_id"])
    if action.tool == "restore_from_quarantine":
        return quarantine.restore_from_quarantine(action.params["batch_id"])
    if action.tool == "stop_process":
        return stop_process(action.params["pid"])
    raise ValueError(f"no dispatcher for tool {action.tool!r}")
