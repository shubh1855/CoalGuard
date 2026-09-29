# ui/compliance.py
import streamlit as st
import pandas as pd
from datetime import datetime
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
from database import SessionLocal, ComplianceItem, Site, AlertLog
from i18n import t


def render(site_filter=None):
    st.subheader(t("compliance.title"))

    db = SessionLocal()
    sites = db.query(Site).all()
    site_names = {s.id: s.name for s in sites}

    col1, col2, col3 = st.columns(3)
    with col1:
        selected_site_name = st.selectbox(t("compliance.mine_site"), [t("compliance.all")] + [s.name for s in sites])
    with col2:
        category_filter = st.selectbox(t("compliance.category"), [
            t("compliance.all"), "Safety", "Labour", "Environment", "Production"
        ])
    with col3:
        status_filter = st.selectbox(t("compliance.status"), [
            t("compliance.all"),
            t("compliance.compliant"),
            t("compliance.pending"),
            t("compliance.overdue"),
            t("compliance.in_progress"),
        ])

    # Map translated status back to DB values for filtering
    status_db_map = {
        t("compliance.compliant"): "Compliant",
        t("compliance.pending"): "Pending",
        t("compliance.overdue"): "Overdue",
        t("compliance.in_progress"): "In Progress",
    }

    query = db.query(ComplianceItem)
    if selected_site_name != t("compliance.all"):
        site_id = next(s.id for s in sites if s.name == selected_site_name)
        query = query.filter(ComplianceItem.site_id == site_id)
    if category_filter != t("compliance.all"):
        query = query.filter(ComplianceItem.category == category_filter)
    if status_filter != t("compliance.all"):
        db_status = status_db_map.get(status_filter, status_filter)
        query = query.filter(ComplianceItem.status == db_status)

    items = query.all()

    all_items = db.query(ComplianceItem).all()
    total = len(all_items)
    compliant = sum(1 for i in all_items if i.status == "Compliant")
    overdue = sum(1 for i in all_items if i.status == "Overdue")
    pending = sum(1 for i in all_items if i.status == "Pending")

    c1, c2, c3, c4 = st.columns(4)
    c1.metric(t("compliance.total_requirements"), total)
    c2.metric(t("compliance.compliant"), compliant)
    c3.metric(t("compliance.overdue"), overdue, delta=f"-{overdue}" if overdue else None, delta_color="inverse")
    c4.metric(t("compliance.pending"), pending)

    st.divider()

    if items:
        df = pd.DataFrame([{
            t("compliance.col_site"): site_names.get(i.site_id, "Unknown"),
            t("compliance.col_category"): i.category,
            t("compliance.col_regulation"): i.regulation,
            t("compliance.col_description"): i.description,
            t("compliance.col_due_date"): i.due_date.strftime("%d %b %Y") if i.due_date else "N/A",
            t("compliance.col_status"): i.status,
            t("compliance.col_officer"): i.responsible_officer or t("compliance.unassigned"),
        } for i in items])

        status_col = t("compliance.col_status")

        def style_status(val):
            colors = {
                "Compliant": "background-color: #1a4731; color: #4ade80",
                "Overdue": "background-color: #4a1a1a; color: #f87171",
                "Pending": "background-color: #3a3310; color: #facc15",
                "In Progress": "background-color: #1a2e4a; color: #60a5fa",
            }
            return colors.get(val, "")

        st.dataframe(
            df.style.map(style_status, subset=[status_col]),
            use_container_width=True,
            height=400,
            hide_index=True,
        )
    else:
        st.info(t("compliance.no_match"))

    st.divider()

    with st.expander(t("compliance.update_section")):
        item_options = {f"{site_names.get(i.site_id)} -- {i.regulation}": i.id for i in db.query(ComplianceItem).all()}
        selected_label = st.selectbox(t("compliance.select_item"), list(item_options.keys()))
        new_status = st.selectbox(t("compliance.new_status"), [
            t("compliance.compliant"),
            t("compliance.pending"),
            t("compliance.overdue"),
            t("compliance.in_progress"),
        ])
        remarks = st.text_area(t("compliance.remarks"))
        if st.button(t("compliance.update_btn")):
            item_id = item_options[selected_label]
            item = db.query(ComplianceItem).filter(ComplianceItem.id == item_id).first()
            # Map translated status back to DB value
            db_new_status = status_db_map.get(new_status, new_status)
            item.status = db_new_status
            item.remarks = remarks
            item.last_updated = datetime.utcnow()
            if db_new_status == "Overdue":
                db.add(AlertLog(
                    site_id=item.site_id,
                    alert_type="Compliance",
                    message=f"Overdue: {item.regulation} at {site_names.get(item.site_id)}",
                    severity="High",
                    channel="Dashboard",
                ))
            db.commit()
            st.success(t("compliance.updated_msg"))
            st.rerun()

    db.close()
