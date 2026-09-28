# ui/compliance.py
import streamlit as st
import pandas as pd
from datetime import datetime
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
from database import SessionLocal, ComplianceItem, Site, AlertLog


def render(site_filter=None):
    st.subheader("Statutory Compliance Tracker")

    db = SessionLocal()
    sites = db.query(Site).all()
    site_names = {s.id: s.name for s in sites}

    col1, col2, col3 = st.columns(3)
    with col1:
        selected_site_name = st.selectbox("Mine Site", ["All"] + [s.name for s in sites])
    with col2:
        category_filter = st.selectbox("Category", ["All", "Safety", "Labour", "Environment", "Production"])
    with col3:
        status_filter = st.selectbox("Status", ["All", "Compliant", "Pending", "Overdue", "In Progress"])

    query = db.query(ComplianceItem)
    if selected_site_name != "All":
        site_id = next(s.id for s in sites if s.name == selected_site_name)
        query = query.filter(ComplianceItem.site_id == site_id)
    if category_filter != "All":
        query = query.filter(ComplianceItem.category == category_filter)
    if status_filter != "All":
        query = query.filter(ComplianceItem.status == status_filter)

    items = query.all()

    all_items = db.query(ComplianceItem).all()
    total = len(all_items)
    compliant = sum(1 for i in all_items if i.status == "Compliant")
    overdue = sum(1 for i in all_items if i.status == "Overdue")
    pending = sum(1 for i in all_items if i.status == "Pending")

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Total Requirements", total)
    c2.metric("Compliant", compliant)
    c3.metric("Overdue", overdue, delta=f"-{overdue}" if overdue else None, delta_color="inverse")
    c4.metric("Pending", pending)

    st.divider()

    if items:
        df = pd.DataFrame([{
            "Site": site_names.get(i.site_id, "Unknown"),
            "Category": i.category,
            "Regulation": i.regulation,
            "Description": i.description,
            "Due Date": i.due_date.strftime("%d %b %Y") if i.due_date else "N/A",
            "Status": i.status,
            "Officer": i.responsible_officer or "Unassigned",
        } for i in items])

        def style_status(val):
            colors = {
                "Compliant": "background-color: #1a4731; color: #4ade80",
                "Overdue": "background-color: #4a1a1a; color: #f87171",
                "Pending": "background-color: #3a3310; color: #facc15",
                "In Progress": "background-color: #1a2e4a; color: #60a5fa",
            }
            return colors.get(val, "")

        st.dataframe(
            df.style.map(style_status, subset=["Status"]),
            width='stretch',
            height=400,
        )
    else:
        st.info("No compliance items match the current filters.")

    st.divider()

    with st.expander("Update Compliance Status"):
        item_options = {f"{site_names.get(i.site_id)} -- {i.regulation}": i.id for i in db.query(ComplianceItem).all()}
        selected_label = st.selectbox("Select Item", list(item_options.keys()))
        new_status = st.selectbox("New Status", ["Compliant", "Pending", "Overdue", "In Progress"])
        remarks = st.text_area("Remarks")
        if st.button("Update"):
            item_id = item_options[selected_label]
            item = db.query(ComplianceItem).filter(ComplianceItem.id == item_id).first()
            item.status = new_status
            item.remarks = remarks
            item.last_updated = datetime.utcnow()
            if new_status == "Overdue":
                db.add(AlertLog(
                    site_id=item.site_id,
                    alert_type="Compliance",
                    message=f"Overdue: {item.regulation} at {site_names.get(item.site_id)}",
                    severity="High",
                    channel="Dashboard",
                ))
            db.commit()
            st.success("Updated.")
            st.rerun()

    db.close()
