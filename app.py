import os
import streamlit as st

from pcsense.telemetry.collectors import collect_evidence
from pcsense.telemetry.health import health_score
from pcsense import orchestrator
from pcsense.contracts import Plan
from pcsense.safety.audit import read_all as read_audit_log
from pcsense.ui.cyber_theme import load_cyber_theme

st.set_page_config(page_title="PCSense", layout="wide")
load_cyber_theme()

# -- Session State --
st.session_state.setdefault("feed", [])
st.session_state.setdefault("plan", None)
st.session_state.setdefault("simulation", None)
st.session_state.setdefault("pending_action_ids", [])
st.session_state.setdefault("verification", None)
st.session_state.setdefault("history", [])  # [(ts, cpu, ram), ...] for the trend chart
st.session_state.setdefault("refresh_nonce", 0)

# -- Sidebar --
st.sidebar.title("PCSense Settings")
autonomy_level = st.sidebar.selectbox(
    "Autonomy Level",
    options=[0, 1, 2],
    format_func=lambda x: {0: "Observe", 1: "Ask (Default)", 2: "Auto-low-risk"}[x],
    index=1,
)
st.sidebar.markdown(f"**Model:** `{os.environ.get('PCSENSE_MODEL', 'gemma4:e2b')}`")
_sandbox_display = os.environ.get("PCSENSE_SANDBOX", r"C:\pcsense_sandbox")
st.sidebar.markdown(f"**Sandbox:** `{_sandbox_display}`")
st.sidebar.markdown(f"**Cached Mode:** `{'ON' if os.environ.get('PCSENSE_CACHED', '0') == '1' else 'OFF'}`")
if st.sidebar.button("⟳ Refresh telemetry now"):
    st.session_state.refresh_nonce += 1


# -- Dashboard telemetry (cached) --------------------------------------------
# collect_evidence() blocks for ~2.8s (CPU priming + I/O-delta sampling) by design — it's a
# real measurement, not a bug. Calling it unmemoized meant EVERY Streamlit rerun (every
# click, every keypress-enter, every tab switch) re-paid that 2.8s and visually looked like
# the whole page "reset". Caching means only an actual refresh (timeout or the sidebar
# button) pays that cost; everything else reuses the last reading instantly.
@st.cache_data(ttl=8, show_spinner="Reading live telemetry...")
def _cached_evidence(nonce: int):
    # `nonce` (no leading underscore) is deliberately part of the cache key — Streamlit
    # excludes underscore-prefixed params from hashing, which would make the sidebar
    # "Refresh" button a no-op since it only works by changing this value.
    return collect_evidence(top_n=6)


evidence = _cached_evidence(st.session_state.refresh_nonce)
score, breakdown = health_score(evidence)

st.title("PCSENSE // TERMINAL.ACCESS")

c1, c2, c3, c4, c5 = st.columns(5)
c1.metric("CPU", f"{evidence.cpu_percent}%")
c2.metric("RAM", f"{evidence.ram_percent}%")
c3.metric("Disk Free", f"{evidence.free_gb} GB")
c4.metric("Swap", f"{evidence.swap_percent}%" if evidence.swap_percent is not None else "N/A")
with c5:
    st.metric("Health Score", f"{score}/100")
    if breakdown:
        with st.expander("Why?"):
            for reason, penalty in breakdown:
                st.write(f"{reason} ({penalty})")

# -- Trend chart --------------------------------------------------------------
history = st.session_state.history
if not history or history[-1][0] != evidence.ts:
    history.append((evidence.ts, evidence.cpu_percent, evidence.ram_percent))
    st.session_state.history = history[-60:]  # cap so the chart doesn't grow forever

if len(st.session_state.history) >= 2:
    import pandas as pd

    chart_df = pd.DataFrame(st.session_state.history, columns=["ts", "CPU %", "RAM %"]).set_index("ts")
    st.line_chart(chart_df, height=180)
else:
    st.caption("Trend chart fills in after a couple of telemetry refreshes.")

with st.expander(f"Top {len(evidence.top_processes)} processes by memory"):
    st.table(
        [
            {"Process": p.name, "PID": p.pid, "RAM (GB)": p.mem_gb, "CPU %": p.cpu_percent, "I/O MB/s": p.io_mb_s}
            for p in evidence.top_processes
        ]
    )

st.divider()

# -- Tabs --
tab_main, tab_audit, tab_eval = st.tabs(["Agent", "Audit Log", "Eval Results"])

with tab_main:
    with st.form("request_form", clear_on_submit=False):
        request_text = st.text_input(
            "SYS.PROMPT>", placeholder="> EXECUTE DIRECTIVE (e.g., Free up 3 GB)"
        )
        submitted_request = st.form_submit_button("Submit Request")

    if submitted_request and request_text:
        st.session_state.feed = []
        st.session_state.plan = None
        st.session_state.simulation = None
        st.session_state.pending_action_ids = []
        st.session_state.verification = None

        with st.spinner("Gathering telemetry and diagnosing... (this re-measures the system, ~3s)"):
            for event in orchestrator.run(request_text, autonomy_level):
                if event.kind == "step":
                    tool = event.payload.get("tool", "?")
                    st.session_state.feed.append(f"🤖 step: {tool}")
                elif event.kind == "evidence":
                    st.session_state.feed.append(
                        f"📊 evidence: CPU {event.payload['cpu_percent']}% · "
                        f"RAM {event.payload['ram_percent']}% · Free {event.payload['free_gb']} GB"
                    )
                elif event.kind == "diagnosis" and "hypotheses" in event.payload:
                    primary = event.payload["primary"]
                    label = f"{primary['name']} ({primary['confidence']:.0%})" if primary else "no clear cause"
                    st.session_state.feed.append(f"🔍 primary cause: {label}")
                    st.session_state["diagnosis_detail"] = event.payload
                elif event.kind == "diagnosis" and "explanation" in event.payload:
                    st.session_state["explanation_detail"] = event.payload["explanation"]
                elif event.kind == "plan":
                    st.session_state.plan = event.payload["plan"]
                    st.session_state.simulation = event.payload.get("simulation")
                    st.session_state.feed.append(f"📋 plan: {len(event.payload['plan']['actions'])} action(s) proposed")
                elif event.kind == "approval_request":
                    # Previously discarded entirely (`pass`) — action_ids is exactly which
                    # actions still need a human decision (some may have already auto-run at
                    # autonomy=2); without tracking it, the UI showed every plan action as
                    # approvable even ones that already executed or never needed approval.
                    st.session_state.pending_action_ids = event.payload["action_ids"]
                elif event.kind == "action_result":
                    status = "✅" if event.payload["ok"] else "⛔"
                    st.session_state.feed.append(f"{status} {event.payload['detail']}")
                elif event.kind == "verify":
                    st.session_state.verification = event.payload
                elif event.kind == "error":
                    st.session_state.feed.append(f"⚠️ {event.payload.get('reason', 'unknown error')}")
        st.rerun()

    # Agent Feed
    if st.session_state.feed:
        st.subheader("Agent Activity")
        for line in st.session_state.feed:
            st.text(line)

    # Diagnosis detail
    diagnosis_detail = st.session_state.get("diagnosis_detail")
    if diagnosis_detail:
        st.subheader("Diagnosis")
        primary = diagnosis_detail["primary"]
        if primary:
            st.write(f"**Primary cause:** {primary['name']} — confidence {primary['confidence']:.0%}")
        else:
            st.write("No primary cause identified with high confidence.")
        for h in diagnosis_detail["secondary"]:
            st.caption(f"Secondary contributor: {h['name']} ({h['confidence']:.0%})")
        for note in diagnosis_detail["normal"]:
            st.caption(f"Normal: {note}")

    explanation_detail = st.session_state.get("explanation_detail")
    if explanation_detail:
        st.markdown(f"**{explanation_detail['headline']}**")
        for line in explanation_detail["observed"]:
            st.write(f"- Observed: {line}")
        for line in explanation_detail["inferred"]:
            st.write(f"- Inferred: {line}")
        for line in explanation_detail["uncertain"]:
            st.write(f"- Uncertain: {line}")

    # Plan View
    if st.session_state.plan:
        st.subheader("Proposed Plan")
        plan = st.session_state.plan
        st.write(f"**Goal:** {plan['goal']}")

        simulation = st.session_state.simulation
        if simulation and simulation.get("notes"):
            st.markdown("**What-if simulation**")
            for note in simulation["notes"]:
                st.caption(f"↳ {note}")

        pending_ids = set(st.session_state.pending_action_ids)
        pending_actions = [a for a in plan["actions"] if a["id"] in pending_ids]

        if autonomy_level == 0:
            st.info("Observe mode: the plan is shown for review only — Execute is disabled at this autonomy level.")
            for act in plan["actions"]:
                color = {"LOW": "green", "MEDIUM": "orange", "HIGH": "red"}.get(act["risk"], "gray")
                st.markdown(f"- [{act['risk']}] {act['tool']} — {act['rationale']}")
        elif not pending_actions:
            st.success("Every action in this plan already auto-executed (Auto-low-risk, LOW-risk only) — nothing left to approve.")
        else:
            approved_ids = []
            with st.form("plan_approval_form"):
                for act in pending_actions:
                    cols = st.columns([1, 4, 1])
                    checked = cols[0].checkbox(act["tool"], value=True, key=f"approve_{act['id']}")
                    if checked:
                        approved_ids.append(act["id"])

                    cols[1].write(act["rationale"])
                    if act["tool"] == "stop_process":
                        cols[1].warning("⚠️ This will forcibly terminate the process.")
                    elif act["tool"] == "empty_quarantine":
                        cols[1].error("🚨 This will permanently delete quarantined files.")

                    color = {"LOW": "green", "MEDIUM": "orange", "HIGH": "red"}.get(act["risk"], "gray")
                    cols[2].markdown(f"**<span style='color:{color}'>{act['risk']}</span>**", unsafe_allow_html=True)

                st.markdown("---")
                if plan.get("excluded"):
                    st.write("**Not touching:**")
                    for excl in plan["excluded"]:
                        st.write(f"- `{excl['name']}`: {excl['reason']}")

                submitted_approval = st.form_submit_button("Approve & Execute")
                if submitted_approval:
                    with st.spinner("Executing and running verification... (this re-measures the system, ~5s)"):
                        for event in orchestrator.execute_approved(Plan(**plan), approved_ids):
                            if event.kind == "action_result":
                                status = "✅" if event.payload["ok"] else "⛔"
                                st.session_state.feed.append(f"{status} {event.payload['detail']}")
                            elif event.kind == "verify":
                                st.session_state.verification = event.payload
                    st.session_state.plan = None
                    st.session_state.pending_action_ids = []
                    st.rerun()

    # Verification Panel
    if st.session_state.verification:
        st.subheader("Verification Results")
        vf = st.session_state.verification
        if vf["improved"]:
            st.success(vf["summary"])
        else:
            st.error(vf["summary"])

        before_after_cols = st.columns(2)
        before_after_cols[0].markdown("**Before**")
        before_after_cols[0].json(vf["before"])
        before_after_cols[1].markdown("**After**")
        before_after_cols[1].json(vf["after"])

with tab_audit:
    st.subheader("Audit Log")
    entries = read_audit_log()
    if not entries:
        st.caption("No audit entries yet — submit a request to generate some.")
    else:
        st.table(
            [
                {"ts": e.ts, "kind": e.kind, "summary": str(e.payload)[:120]}
                for e in reversed(entries[-50:])
            ]
        )

with tab_eval:
    try:
        with open("eval/results/latest.md", "r") as f:
            st.markdown(f.read())
    except FileNotFoundError:
        st.info("No eval results found. Run `make eval`.")
