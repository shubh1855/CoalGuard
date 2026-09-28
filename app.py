# app.py — CoalGuard entry point
import streamlit as st
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from database import init_db

init_db()

st.set_page_config(
    page_title="CoalGuard",
    page_icon="⛏️",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.sidebar.title("⛏️ CoalGuard")
st.sidebar.caption("AI-Enabled Governance Platform for Coal Mining")
st.sidebar.divider()

page = st.sidebar.radio("Navigate", [
    "Dashboard",
    "Live Safety Monitor",
    "Compliance Tracker",
    "Inspection Management",
    "Mine Site Map",
    "Reports",
])

st.sidebar.divider()
st.sidebar.caption("WIET Hackverse 2.0 | Team Code Crusaders")

if page == "Dashboard":
    from ui.dashboard import render
    render()
elif page == "Live Safety Monitor":
    from ui.live_monitor import render
    render()
elif page == "Compliance Tracker":
    from ui.compliance import render
    render()
elif page == "Inspection Management":
    from ui.inspections import render
    render()
elif page == "Mine Site Map":
    from ui.map_view import render
    render()
elif page == "Reports":
    from ui.reports import render
    render()
