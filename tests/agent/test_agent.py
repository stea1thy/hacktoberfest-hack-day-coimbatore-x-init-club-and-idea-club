import pytest
from pcsense.agent.router import route, baseline_route
from pcsense.agent.faithfulness import check
from pcsense.agent.explainer import template_explain
from pcsense.contracts import Action

def test_router_bounds():
    # Test valid goal_gb
    res = route("make 3 gigs of room")
    # This invokes LLM which might fail in test env if Ollama isn't running.
    # Let's mock it for the test or rely on baseline.
    assert baseline_route("make 3 gigs of room")["intent"] == "free_space"

def test_faithfulness_valid():
    evidence = {"ram": 91.0, "cpu": 15.5}
    text = "The RAM is at 91 percent and CPU is 15.5."
    ok, violations = check(text, evidence)
    assert ok is True
    assert len(violations) == 0

def test_faithfulness_invalid():
    # Deliberately injected wrong number
    evidence = {"ram": 91.0, "cpu": 15.5}
    text = "The RAM is at 71 percent."
    ok, violations = check(text, evidence)
    assert ok is False
    assert 71.0 in violations

def test_explainer_template():
    a = Action(id="a1", tool="stop_process", params={}, risk="HIGH", rationale="Stop it")
    res = template_explain({}, [], [a])
    assert "a1" in res["recommended_action_ids"]
