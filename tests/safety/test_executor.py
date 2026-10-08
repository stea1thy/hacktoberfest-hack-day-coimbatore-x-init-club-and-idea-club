"""Adversarial tests for pcsense/safety/executor.py — plan-hash binding (§4.8-7) and the
policy-gate / audit-log path. The model must not be able to swap actions after a human
approves the plan.
"""
from __future__ import annotations

from pcsense.contracts import Action, Plan
from pcsense.safety import audit, executor, policy


def _action(action_id: str, tool: str, params: dict, risk: str = "LOW", est_bytes: int = 0) -> Action:
    return Action(id=action_id, tool=tool, params=params, risk=risk, est_bytes=est_bytes, rationale="test")


def test_tampered_action_list_after_approval_is_refused(sandbox_root):
    original = [_action("a1", "quarantine_paths", {"paths": [str(sandbox_root / "Temp" / "old.log")]})]
    plan_hash = policy.compute_plan_hash(original)

    tampered = [
        _action("a1", "quarantine_paths", {"paths": [str(sandbox_root / "Temp" / "old.log")]}),
        _action("a2", "stop_process", {"pid": 99999}, risk="HIGH"),
    ]
    plan = Plan(goal="free up space", actions=tampered, plan_hash=plan_hash)

    results = executor.run(plan, ["a1", "a2"])
    assert all(r.ok is False for r in results)
    assert all("plan_hash" in r.detail.lower() for r in results)


def test_plan_hash_mismatch_is_audited_as_denial(sandbox_root):
    action = _action("a1", "quarantine_paths", {"paths": [str(sandbox_root / "Temp" / "old.log")]})
    plan = Plan(goal="free up space", actions=[action], plan_hash="not-the-real-hash")

    executor.run(plan, ["a1"])

    entries = audit.read_all()
    assert any(e.kind == "denial" and "plan_hash" in e.payload.get("reason", "").lower() for e in entries)


def test_policy_denial_is_not_executed(sandbox_root):
    """A policy-denied action must never reach quarantine/executor filesystem code."""
    outside_path = str(sandbox_root.parent / "outside.txt")
    action = _action("a1", "quarantine_paths", {"paths": [outside_path]})
    plan = Plan(goal="free up space", actions=[action], plan_hash=policy.compute_plan_hash([action]))

    results = executor.run(plan, ["a1"])

    assert results[0].ok is False
    assert results[0].bytes_moved == 0


def test_approved_and_allowed_action_executes_and_logs_result(sandbox_root):
    target = sandbox_root / "Temp" / "old.log"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("junk")

    action = _action("a1", "quarantine_paths", {"paths": [str(target)]}, est_bytes=4)
    plan = Plan(goal="free up space", actions=[action], plan_hash=policy.compute_plan_hash([action]))

    results = executor.run(plan, ["a1"])

    assert results[0].ok is True
    assert not target.exists()  # moved into quarantine, not left in place
    entries = audit.read_all()
    assert any(e.kind == "result" and e.payload.get("action_id") == "a1" for e in entries)
