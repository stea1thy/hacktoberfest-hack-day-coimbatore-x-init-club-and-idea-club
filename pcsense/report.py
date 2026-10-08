"""End-of-session report (PCSense_Complete_Feature_Specification.txt §12, scaled down from
daily/weekly to a single demo session): summarizes what happened by reading the audit log plus
a fresh health-score snapshot. Read-only.

New top-level module, same reasoning as pcsense/simulate.py.
"""
from __future__ import annotations

from pcsense.safety import audit
from pcsense.telemetry.collectors import collect_evidence
from pcsense.telemetry.health import health_score


def end_of_session_report() -> dict:
    entries = audit.read_all()

    requests = [e for e in entries if e.kind == "request"]
    results = [e for e in entries if e.kind == "result"]
    denials = [e for e in entries if e.kind == "denial"]
    verifies = [e for e in entries if e.kind == "verify"]

    succeeded = [r for r in results if r.payload.get("ok")]
    bytes_recovered = sum(r.payload.get("bytes", 0) for r in succeeded)
    processes_stopped = sum(1 for r in succeeded if "terminated pid" in str(r.payload.get("detail", "")))
    improved_count = sum(1 for v in verifies if v.payload.get("improved"))

    evidence = collect_evidence()
    health = health_score(evidence)

    return {
        "requests_handled": len(requests),
        "actions_succeeded": len(succeeded),
        "actions_denied": len(denials),
        "bytes_recovered": bytes_recovered,
        "processes_stopped": processes_stopped,
        "fixes_verified_improved": improved_count,
        "fixes_verified_total": len(verifies),
        "current_health_score": health["score"],
        "current_health_deductions": health["deductions"],
    }
