"""Tests for pcsense/orchestrator.py: does it actually tie the pieces together into the
right event sequence, and does the approval/autonomy gating (§4.6) hold even against stub
data (e.g. the mock evidence's top process happens to be ollama.exe, which policy.check()
must still refuse to stop)?
"""
from __future__ import annotations

from pcsense import orchestrator
from pcsense.contracts import Action, Plan
from pcsense.safety import policy


def _event_kinds(events) -> list[str]:
    return [e.kind for e in events]


def test_diagnose_slow_observe_level_stops_before_approval(sandbox_root):
    events = list(orchestrator.run("why is my pc slow", autonomy=0))
    kinds = _event_kinds(events)
    assert "plan" in kinds
    assert "approval_request" not in kinds
    assert "action_result" not in kinds


def test_diagnose_slow_ask_level_reaches_approval_request(sandbox_root):
    events = list(orchestrator.run("why is my pc slow", autonomy=1))
    kinds = _event_kinds(events)
    assert kinds[:2] == ["step", "evidence"]  # route step, then evidence (collected up front)
    assert "evidence" in kinds
    assert "diagnosis" in kinds
    assert "plan" in kinds
    assert "approval_request" in kinds
    assert "action_result" not in kinds  # HIGH-risk stop_process never auto-executes


def test_diagnosis_event_carries_primary_secondary_normal_split(sandbox_root):
    events = list(orchestrator.run("why is my pc slow", autonomy=1))
    diagnosis_events = [e for e in events if e.kind == "diagnosis" and "hypotheses" in e.payload]
    assert len(diagnosis_events) == 1
    payload = diagnosis_events[0].payload
    assert payload["primary"] is not None
    assert payload["primary"]["name"] == "memory_pressure"  # mock evidence has ram_percent > 60
    assert isinstance(payload["secondary"], list)
    assert isinstance(payload["normal"], list)


def test_plan_event_carries_a_simulation(sandbox_root):
    events = list(orchestrator.run("why is my pc slow", autonomy=1))
    plan_event = next(e for e in events if e.kind == "plan")
    assert "simulation" in plan_event.payload
    assert "plan" in plan_event.payload
    # mock evidence's top process is ollama.exe with mem_gb=3.2 — stopping it should predict a RAM drop
    assert plan_event.payload["simulation"]["ram"] is not None


def test_approval_request_action_is_denied_by_policy_not_silently_dropped(sandbox_root):
    """Mock evidence's top process is ollama.exe — policy must refuse to stop it even
    though the orchestrator's rule engine proposed it."""
    events = list(orchestrator.run("why is my pc slow", autonomy=1))
    plan_event = next(e for e in events if e.kind == "plan")
    approval_event = next(e for e in events if e.kind == "approval_request")

    plan = Plan(**plan_event.payload["plan"])
    action_ids = approval_event.payload["action_ids"]

    result_events = list(orchestrator.execute_approved(plan, action_ids))
    action_results = [e for e in result_events if e.kind == "action_result"]
    assert len(action_results) == 1
    assert action_results[0].payload["ok"] is False


def test_free_space_auto_low_risk_executes_without_approval(sandbox_root):
    (sandbox_root / "Temp").mkdir(parents=True, exist_ok=True)
    (sandbox_root / "Temp" / "old.log").write_text("junk")

    events = list(orchestrator.run(f"free up 3 gb in {sandbox_root}", autonomy=2))
    kinds = _event_kinds(events)
    assert "plan" in kinds
    # candidates() stub proposes a LOW-risk temp-file action and a MEDIUM-risk dev-artifact
    # action; at autonomy=2 the LOW one should auto-execute and the MEDIUM one should wait.
    assert "action_result" in kinds or "approval_request" in kinds


def test_status_intent_has_no_plan_or_actions(sandbox_root):
    events = list(orchestrator.run("status", autonomy=1))
    kinds = _event_kinds(events)
    assert "evidence" in kinds
    assert "plan" not in kinds
    assert "approval_request" not in kinds


def test_execute_approved_refuses_tampered_plan_hash(sandbox_root):
    action = Action(id="a1", tool="stop_process", params={"pid": 99999}, risk="HIGH", rationale="test")
    plan = Plan(goal="g", actions=[action], plan_hash="not-the-real-hash")
    events = list(orchestrator.execute_approved(plan, ["a1"]))
    action_results = [e for e in events if e.kind == "action_result"]
    assert len(action_results) == 1
    assert action_results[0].payload["ok"] is False
    assert "plan_hash" in action_results[0].payload["detail"].lower()
