"""End-of-session report (PCSense_Complete_Feature_Specification.txt §12, scaled to a session)."""
from __future__ import annotations

from pcsense.report import end_of_session_report
from pcsense.safety import audit


def test_empty_session_reports_zeros_but_still_includes_health(sandbox_root):
    report = end_of_session_report()
    assert report["requests_handled"] == 0
    assert report["actions_succeeded"] == 0
    assert report["actions_denied"] == 0
    assert report["bytes_recovered"] == 0
    assert "current_health_score" in report
    assert isinstance(report["current_health_deductions"], list)


def test_report_tallies_requests_results_denials_and_verifies(sandbox_root):
    audit.log("request", {"text": "free up 3gb", "autonomy": 1})
    audit.log("request", {"text": "why is my pc slow", "autonomy": 1})
    audit.log("result", {"action_id": "a1", "ok": True, "bytes": 5_000_000_000, "detail": "quarantined"})
    audit.log("result", {"action_id": "a2", "ok": True, "bytes": 0, "detail": "terminated pid 123"})
    audit.log("result", {"action_id": "a3", "ok": False, "detail": "denied"})
    audit.log("denial", {"action_id": "a4", "reason": "sandbox marker missing"})
    audit.log("verify", {"before": {}, "after": {}, "improved": True, "summary": "ok"})
    audit.log("verify", {"before": {}, "after": {}, "improved": False, "summary": "no change"})

    report = end_of_session_report()

    assert report["requests_handled"] == 2
    assert report["actions_succeeded"] == 2
    assert report["actions_denied"] == 1
    assert report["bytes_recovered"] == 5_000_000_000
    assert report["processes_stopped"] == 1
    assert report["fixes_verified_improved"] == 1
    assert report["fixes_verified_total"] == 2
