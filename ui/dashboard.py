# ui/dashboard.py
import streamlit as st
import pandas as pd
import altair as alt
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
from database import SessionLocal, Site, Violation, ComplianceItem, Inspection, AlertLog


def render():
    db = SessionLocal()
    sites = db.query(Site).all()
    violations = db.query(Violation).all()
    compliance_items = db.query(ComplianceItem).all()
    inspections = db.query(Inspection).all()
    alerts = db.query(AlertLog).order_by(AlertLog.sent_at.desc()).limit(10).all()

    st.subheader("Operations Overview")

    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Active Mine Sites", len(sites))
    c2.metric("Total Violations (CV)", len(violations))
    overdue = sum(1 for i in compliance_items if i.status == "Overdue")
    c3.metric("Overdue Compliance", overdue)
    open_insp = sum(1 for i in inspections if i.status in ["Open", "Action Pending"])
    c4.metric("Open Inspections", open_insp)
    critical = sum(1 for i in inspections if i.severity == "Critical")
    c5.metric("Critical Findings", critical)

    st.divider()

    col_left, col_right = st.columns([3, 2])

    with col_left:
        st.markdown("**Compliance Status Distribution**")
        if compliance_items:
            status_counts = pd.DataFrame(
                [{"Status": i.status} for i in compliance_items]
            )["Status"].value_counts().reset_index()
            status_counts.columns = ["Status", "Count"]
            chart = alt.Chart(status_counts).mark_bar().encode(
                x=alt.X("Status:N"),
                y=alt.Y("Count:Q"),
                color=alt.Color("Status:N", scale=alt.Scale(
                    domain=["Compliant", "Pending", "Overdue", "In Progress"],
                    range=["#4ade80", "#facc15", "#f87171", "#60a5fa"]
                ))
            ).properties(height=250)
            st.altair_chart(chart, use_container_width=True)

    with col_right:
        st.markdown("**Recent Alerts**")
        for a in alerts:
            color = {"High": "🔴", "Critical": "🚨", "Medium": "🟡", "Low": "🟢"}.get(a.severity, "⚪")
            msg = a.message[:70] + "..." if len(a.message) > 70 else a.message
            st.markdown(f"{color} `{a.alert_type}` — {msg}")
            st.caption(a.sent_at.strftime("%d %b %Y %H:%M"))

    st.divider()

    st.markdown("**Violations Over Time**")
    if violations:
        df = pd.DataFrame([{"timestamp": v.timestamp, "type": v.violation_type} for v in violations])
        df["date"] = pd.to_datetime(df["timestamp"]).dt.date
        daily = df.groupby("date").size().reset_index(name="count")
        chart2 = alt.Chart(daily).mark_line(point=True).encode(
            x="date:T", y="count:Q"
        ).properties(height=200)
        st.altair_chart(chart2, use_container_width=True)
    else:
        st.info("No CV violations recorded yet.")

    db.close()
