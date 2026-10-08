"""Streamlit entry point. Owner: P2 (after telemetry core works) — this stub now also wires in
orchestrator.run()/execute_approved() end-to-end (diagnosis split, what-if simulation, approval
gate, session report) so those features are actually demoable, not just unit-tested. P2 should
feel free to redesign the layout; the event-handling logic here is the part worth keeping.
"""
import streamlit as st

from pcsense import orchestrator
from pcsense.contracts import Plan
from pcsense.report import end_of_session_report
from pcsense.telemetry.collectors import collect_evidence
from pcsense.telemetry.health import health_score

st.set_page_config(page_title="PCSense", layout="wide")
st.title("PCSense — local-first AI technician")

evidence = collect_evidence()
health = health_score(evidence)

col1, col2, col3 = st.columns(3)
col1.metric("CPU %", f"{evidence.cpu_percent:.0f}")
col2.metric("RAM %", f"{evidence.ram_percent:.0f}")
col3.metric("Free GB", f"{evidence.free_gb:.1f}")

st.subheader(f"Health score: {health['score']}")
for d in health["deductions"]:
    st.caption(f"-{d['penalty']}  {d['signal']}")

st.divider()

autonomy = st.selectbox(
    "Autonomy level",
    options=[0, 1, 2],
    index=1,
    format_func=lambda n: {0: "0 — Observe", 1: "1 — Ask (default)", 2: "2 — Auto-low-risk"}[n],
)
request_text = st.text_input("Ask PCSense something (e.g. \"why is my pc slow?\" or \"free up 3 gb\")")

if st.button("Run") and request_text:
    events = list(orchestrator.run(request_text, autonomy))
    st.session_state["events"] = events
    st.session_state.pop("approved_result_events", None)

events = st.session_state.get("events", [])

for event in events:
    if event.kind == "diagnosis" and "hypotheses" in event.payload:
        st.markdown("**Diagnosis**")
        primary = event.payload["primary"]
        if primary:
            st.write(f"Primary cause: **{primary['name']}** (confidence {primary['confidence']:.0%})")
        else:
            st.write("No primary cause identified with high confidence.")
        for h in event.payload["secondary"]:
            st.caption(f"Secondary: {h['name']} (confidence {h['confidence']:.0%})")
        for note in event.payload["normal"]:
            st.caption(f"Normal: {note}")

    elif event.kind == "diagnosis" and "explanation" in event.payload:
        explanation = event.payload["explanation"]
        st.markdown(f"**{explanation['headline']}**")
        for line in explanation["observed"]:
            st.write(f"- Observed: {line}")
        for line in explanation["inferred"]:
            st.write(f"- Inferred: {line}")
        for line in explanation["uncertain"]:
            st.write(f"- Uncertain: {line}")

    elif event.kind == "plan":
        st.markdown("**Plan**")
        plan = event.payload["plan"]
        for action in plan["actions"]:
            st.write(f"- [{action['risk']}] {action['tool']} — {action['rationale']}")
        simulation = event.payload["simulation"]
        for note in simulation["notes"]:
            st.caption(f"What-if: {note}")

    elif event.kind == "approval_request":
        plan_dict = event.payload["plan"]
        action_ids = event.payload["action_ids"]
        st.markdown("**Approval needed**")
        st.write(f"Actions awaiting approval: {', '.join(action_ids)}")
        if st.button("Approve selected actions"):
            plan = Plan(**plan_dict)
            st.session_state["approved_result_events"] = list(orchestrator.execute_approved(plan, action_ids))

    elif event.kind == "error":
        st.error(event.payload.get("reason", "unknown error"))

for event in st.session_state.get("approved_result_events", []):
    if event.kind == "action_result":
        status = "OK" if event.payload["ok"] else "DENIED/FAILED"
        st.write(f"[{status}] {event.payload['detail']}")
    elif event.kind == "verify":
        if event.payload["improved"]:
            st.success(event.payload["summary"])
        else:
            st.warning(event.payload["summary"])

st.divider()
with st.expander("Session report"):
    report = end_of_session_report()
    st.json(report)

st.caption("Stub UI — real dashboard, agent feed, risk badges and audit tab land as tracks complete.")
