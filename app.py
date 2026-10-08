import os
import streamlit as st

from pcsense.telemetry.collectors import collect_evidence
from pcsense.telemetry.health import health_score
from pcsense.ui import mock_orchestrator
from pcsense.ui.cyber_theme import load_cyber_theme

st.set_page_config(page_title="PCSense", layout="wide")
load_cyber_theme()

# -- Session State --
if "feed" not in st.session_state:
    st.session_state.feed = []
if "plan" not in st.session_state:
    st.session_state.plan = None
if "verification" not in st.session_state:
    st.session_state.verification = None

# -- Sidebar --
st.sidebar.title("PCSense Settings")
autonomy_level = st.sidebar.selectbox(
    "Autonomy Level", 
    options=[0, 1, 2],
    format_func=lambda x: {0: "Observe", 1: "Ask (Default)", 2: "Auto-low-risk"}[x],
    index=1
)
st.sidebar.markdown(f"**Model:** `{os.environ.get('PCSENSE_MODEL', 'gemma4:e2b')}`")
st.sidebar.markdown(f"**Sandbox:** `{os.environ.get('PCSENSE_SANDBOX', 'C:\\pcsense_sandbox')}`")
st.sidebar.markdown(f"**Cached Mode:** `{'ON' if os.environ.get('PCSENSE_CACHED', '0') == '1' else 'OFF'}`")

# -- Top Metrics --
st.title("PCSENSE // TERMINAL.ACCESS")
try:
    evidence = collect_evidence(top_n=3)
    score, breakdown = health_score(evidence)
except Exception as e:
    evidence = None
    score, breakdown = 100, []

if evidence:
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("CPU", f"{evidence.cpu_percent}%")
    c2.metric("RAM", f"{evidence.ram_percent}%")
    c3.metric("Disk Free", f"{evidence.free_gb} GB")
    
    with c4:
        st.metric("Health Score", f"{score}/100")
        if breakdown:
            with st.expander("Why?"):
                for reason, penalty in breakdown:
                    st.write(f"{reason} ({penalty})")

# -- Tabs --
tab_main, tab_audit, tab_eval = st.tabs(["Agent", "Audit Log", "Eval Results"])

with tab_main:
    # Request Input
    request_text = st.text_input("SYS.PROMPT>", placeholder="> EXECUTE DIRECTIVE (e.g., Free up 3 GB)")
    if st.button("Submit Request") and request_text:
        st.session_state.feed = []
        st.session_state.plan = None
        st.session_state.verification = None
        
        # Start orchestrator
        for event in mock_orchestrator.start(request_text, autonomy_level):
            if event.type == "step":
                st.session_state.feed.append(f"🤖 {event.payload}")
            elif event.type == "evidence":
                st.session_state.feed.append(f"📊 Collected evidence: {event.payload}")
            elif event.type == "diagnosis":
                st.session_state.feed.append(f"🔍 Diagnosis: {event.payload[0]['name']} ({event.payload[0]['confidence']})")
            elif event.type == "plan":
                st.session_state.plan = event.payload
                
        st.rerun()

    # Agent Feed
    if st.session_state.feed:
        st.subheader("Agent Activity")
        for line in st.session_state.feed:
            st.text(line)

    # Plan View
    if st.session_state.plan:
        st.subheader("Proposed Plan")
        plan = st.session_state.plan
        st.write(f"**Goal:** {plan['goal']}")
        
        approved_ids = []
        with st.form("plan_approval_form"):
            for act in plan["actions"]:
                cols = st.columns([1, 4, 1])
                checked = cols[0].checkbox(act["tool"], value=True, key=act["id"])
                if checked:
                    approved_ids.append(act["id"])
                
                cols[1].write(act["rationale"])
                # Explicit warnings for high-risk actions
                if act["tool"] == "stop_process":
                    cols[1].warning("⚠️ This will forcibly terminate the process.")
                elif act["tool"] == "empty_quarantine":
                    cols[1].error("🚨 This will permanently delete quarantined files.")
                
                # Risk badge
                color = {"LOW": "green", "MEDIUM": "orange", "HIGH": "red"}.get(act["risk"], "gray")
                cols[2].markdown(f"**<span style='color:{color}'>{act['risk']}</span>**", unsafe_allow_html=True)
                
            st.markdown("---")
            if plan.get("excluded"):
                st.write("**Not touching:**")
                for excl in plan["excluded"]:
                    st.write(f"- `{excl['name']}`: {excl['reason']}")
            
            submitted = st.form_submit_button("Approve & Execute")
            if submitted:
                # Execute orchestrator
                for event in mock_orchestrator.execute(plan, approved_ids):
                    if event.type == "step":
                        st.session_state.feed.append(f"🤖 {event.payload}")
                    elif event.type == "action_result":
                        st.session_state.feed.append(f"✅ Action {event.payload['action_id']}: {event.payload['detail']}")
                    elif event.type == "verify":
                        st.session_state.verification = event.payload
                st.session_state.plan = None
                st.rerun()

    # Verification Panel
    if st.session_state.verification:
        st.subheader("Verification Results")
        vf = st.session_state.verification
        if vf["improved"]:
            st.success(vf["summary"])
        else:
            st.error(vf["summary"])
            
        st.json({"Before": vf["before"], "After": vf["after"]})

with tab_audit:
    st.write("Audit log will appear here (SQLite).")

with tab_eval:
    try:
        with open("eval/results/latest.md", "r") as f:
            st.markdown(f.read())
    except FileNotFoundError:
        st.info("No eval results found. Run `make eval`.")
