"""Streamlit entry point. Owner: P2 (after telemetry core works). This is a stub so
`streamlit run app.py` boots end to end on mock data from minute 30.
"""
import streamlit as st

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

st.text_input("Ask PCSense something (e.g. \"why is my PC slow?\")")
st.info("Stub UI — real dashboard, agent feed, plan view and approval gate land as tracks complete.")
