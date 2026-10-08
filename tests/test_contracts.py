"""Contract tests: every stubbed module function must return the type contracts.py promises.

Owner: P1. These are the gate for "does the skeleton actually hold together" — if a stub's
signature or return type drifts from PCSENSE.md §8, this test catches it before teammates build
on top of it.
"""
from __future__ import annotations

from pcsense import orchestrator
from pcsense.agent.loop import run_loop
from pcsense.contracts import (
    Action,
    ActionResult,
    Decision,
    Evidence,
    Explanation,
    Hypothesis,
    RouterOut,
    VerifyResult,
)
from pcsense.safety.audit import log
from pcsense.safety.executor import run as executor_run
from pcsense.safety.policy import check as policy_check
from pcsense.storage.candidates import candidates
from pcsense.storage.duplicates import find_duplicates
from pcsense.storage.scanner import scan
from pcsense.telemetry.collectors import collect_evidence
from pcsense.telemetry.diagnosis import diagnose
from pcsense.verify.verify import after as verify_after
from pcsense.verify.verify import before as verify_before


def test_collect_evidence_returns_evidence():
    evidence = collect_evidence()
    assert isinstance(evidence, Evidence)


def test_diagnose_returns_hypothesis_list():
    hypotheses = diagnose(collect_evidence())
    assert isinstance(hypotheses, list)
    assert all(isinstance(h, Hypothesis) for h in hypotheses)


def test_scan_returns_list():
    assert isinstance(scan("C:\\pcsense_sandbox"), list)


def test_find_duplicates_returns_list():
    assert isinstance(find_duplicates("C:\\pcsense_sandbox"), list)


def test_candidates_returns_action_list():
    result = candidates("C:\\pcsense_sandbox")
    assert isinstance(result, list)
    assert all(isinstance(a, Action) for a in result)


def test_route_returns_router_out():
    # agent/router.py's route() hits Ollama directly and has no internal fallback; the real
    # contract boundary is orchestrator._route_with_fallback(), which PCSENSE_CACHED=1 (set
    # globally for tests — see tests/conftest.py) routes through baseline_route() instead of
    # a live, slow-to-fail network call.
    assert isinstance(orchestrator._route_with_fallback("why is my pc slow"), RouterOut)


def test_run_loop_returns_tool_results(monkeypatch):
    # run_loop(intent, params) -> list[dict] now (no Evidence — that comes from
    # telemetry.collectors.collect_evidence() directly; see orchestrator.run()). Its own
    # Gemma-step loop would otherwise make one real (slow, here ~10s+) Ollama attempt before
    # giving up; monkeypatch that closed so this stays a fast type-contract check.
    def _no_llm(*args, **kwargs):
        raise RuntimeError("no llm in tests")

    monkeypatch.setattr("pcsense.agent.loop.call_schema", _no_llm)
    tool_results = run_loop("diagnose_slow", {})
    assert isinstance(tool_results, list)


def test_explain_returns_explanation():
    evidence = collect_evidence()
    hypotheses = diagnose(evidence)
    actions = candidates("C:\\pcsense_sandbox")
    # agent/explainer.py's explain() returns a plain dict and expects hypotheses as
    # list[dict] (it calls h.get(...) internally — AttributeErrors on a Hypothesis object).
    # orchestrator._explain_with_fallback() is the real boundary that converts both ways.
    explanation = orchestrator._explain_with_fallback(evidence, hypotheses, actions)
    assert isinstance(explanation, Explanation)
    assert set(explanation.recommended_action_ids).issubset({a.id for a in actions})


def test_policy_check_returns_decision():
    action = Action(id="a1", tool="quarantine_paths", params={}, risk="LOW", rationale="test")
    assert isinstance(policy_check(action), Decision)


def test_executor_run_returns_action_results():
    action = Action(id="a1", tool="quarantine_paths", params={}, risk="LOW", rationale="test")
    from pcsense.contracts import Plan

    plan = Plan(goal="free up space", actions=[action], plan_hash="deadbeef")
    results = executor_run(plan, ["a1"])
    assert isinstance(results, list)
    assert all(isinstance(r, ActionResult) for r in results)


def test_verify_before_after_and_compare_return_verify_result():
    from pcsense.verify.verify import compare

    result = compare(verify_before(), verify_after())
    assert isinstance(result, VerifyResult)


def test_audit_log_returns_audit_entry():
    from pcsense.contracts import AuditEntry

    entry = log("request", {"text": "why is my pc slow"})
    assert isinstance(entry, AuditEntry)
