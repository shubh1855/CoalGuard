# ui/inspections.py
import streamlit as st
import pandas as pd
from datetime import datetime
import os
import sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
from database import SessionLocal, Inspection, CorrectiveAction, Site, AlertLog
from i18n import t


def render():
    st.subheader(t("inspections.title"))

    db = SessionLocal()
    sites = db.query(Site).all()
    site_map = {s.id: s.name for s in sites}

    tab1, tab2, tab3 = st.tabs([t("inspections.tab_all"), t("inspections.tab_new"), t("inspections.tab_actions")])

    with tab1:
        inspections = db.query(Inspection).order_by(Inspection.date.desc()).all()
        if inspections:
            df = pd.DataFrame([{
                t("inspections.col_id"): i.id,
                t("inspections.col_site"): site_map.get(i.site_id, "Unknown"),
                t("inspections.col_type"): i.inspection_type,
                t("inspections.col_inspector"): i.inspector_name,
                t("inspections.col_date"): i.date.strftime("%d %b %Y %H:%M"),
                t("inspections.col_severity"): i.severity,
                t("inspections.col_status"): i.status,
                t("inspections.col_observations"): (i.observations[:80] + "...") if i.observations and len(i.observations) > 80 else i.observations,
            } for i in inspections])

            sev_col = t("inspections.col_severity")

            def style_severity(val):
                m = {"Low": "color: #4ade80", "Medium": "color: #facc15",
                     "High": "color: #fb923c", "Critical": "color: #f87171; font-weight: bold"}
                return m.get(val, "")

            st.dataframe(
                df.style.map(style_severity, subset=[sev_col]),
                use_container_width=True,
                height=400,
                hide_index=True,
            )

            selected_id = st.number_input(t("inspections.enter_id"), min_value=1, step=1)
            if st.button(t("inspections.view_actions_btn")):
                actions = db.query(CorrectiveAction).filter(CorrectiveAction.inspection_id == selected_id).all()
                if actions:
                    for a in actions:
                        st.markdown(f"**{t('inspections.action_label')}:** {a.description}")
                        st.markdown(f"{t('inspections.assigned_to')}: `{a.assigned_to}` | {t('inspections.deadline')}: `{a.deadline.strftime('%d %b %Y') if a.deadline else 'N/A'}` | {t('inspections.col_status')}: `{a.status}`")
                        st.divider()
                else:
                    st.info(t("inspections.no_actions"))
        else:
            st.info(t("inspections.no_inspections"))

    with tab2:
        st.markdown(f"#### {t('inspections.log_title')}")
        col1, col2 = st.columns(2)
        with col1:
            site_name = st.selectbox(t("inspections.site_label"), [s.name for s in sites])
            inspector = st.text_input(t("inspections.inspector_name"))
            insp_type = st.selectbox(t("inspections.inspection_type"), [
                t("inspections.safety"), t("inspections.environmental"), t("inspections.labour")
            ])
            severity = st.selectbox(t("inspections.severity_label"), [
                t("inspections.low"), t("inspections.medium"),
                t("inspections.high"), t("inspections.critical"),
            ])
        with col2:
            lat = st.number_input(t("inspections.latitude"), value=23.75, format="%.6f")
            lon = st.number_input(t("inspections.longitude"), value=86.42, format="%.6f")
            status = st.selectbox(t("inspections.status_label"), [
                t("inspections.open"), t("inspections.action_pending"), t("inspections.closed")
            ])
            image = st.file_uploader(t("inspections.attach_photo"), type=["jpg", "png"])

        observations = st.text_area(t("inspections.observations_label"))

        st.markdown(f"#### {t('inspections.corrective_action_title')}")
        ca_desc = st.text_input(t("inspections.ca_description"))
        ca_assigned = st.text_input(t("inspections.ca_assign_to"))
        ca_deadline = st.date_input(t("inspections.ca_deadline"))

        # Map translated values back to English DB values
        type_db_map = {
            t("inspections.safety"): "Safety",
            t("inspections.environmental"): "Environmental",
            t("inspections.labour"): "Labour",
        }
        severity_db_map = {
            t("inspections.low"): "Low",
            t("inspections.medium"): "Medium",
            t("inspections.high"): "High",
            t("inspections.critical"): "Critical",
        }
        status_db_map = {
            t("inspections.open"): "Open",
            t("inspections.action_pending"): "Action Pending",
            t("inspections.closed"): "Closed",
        }

        if st.button(t("inspections.submit_btn")):
            site_id = next(s.id for s in sites if s.name == site_name)
            img_path = None
            if image:
                os.makedirs("evidence", exist_ok=True)
                img_path = f"evidence/insp_{datetime.utcnow().timestamp()}.jpg"
                with open(img_path, "wb") as f:
                    f.write(image.read())

            db_insp_type = type_db_map.get(insp_type, insp_type)
            db_severity = severity_db_map.get(severity, severity)
            db_status = status_db_map.get(status, status)

            insp = Inspection(
                site_id=site_id,
                inspector_name=inspector,
                inspection_type=db_insp_type,
                latitude=lat,
                longitude=lon,
                observations=observations,
                status=db_status,
                severity=db_severity,
                image_path=img_path,
            )
            db.add(insp)
            db.flush()
            if ca_desc:
                db.add(CorrectiveAction(
                    inspection_id=insp.id,
                    description=ca_desc,
                    assigned_to=ca_assigned,
                    deadline=datetime.combine(ca_deadline, datetime.min.time()),
                    status="Pending",
                ))
            if db_severity in ["High", "Critical"]:
                db.add(AlertLog(
                    site_id=site_id,
                    alert_type="Inspection",
                    message=f"{db_severity} inspection finding at {site_name}: {observations[:100]}",
                    severity=db_severity,
                    channel="Dashboard",
                ))
            db.commit()
            st.success(t("inspections.logged_msg"))
            st.rerun()

    with tab3:
        actions = db.query(CorrectiveAction).filter(CorrectiveAction.status != "Completed").all()
        if actions:
            for a in actions:
                insp = db.query(Inspection).filter(Inspection.id == a.inspection_id).first()
                site_label = site_map.get(insp.site_id, "Unknown") if insp else "Unknown"
                col1, col2 = st.columns([4, 1])
                with col1:
                    st.markdown(f"**{a.description}**  \n{t('inspections.col_site')}: `{site_label}` | {t('inspections.assigned_to')}: `{a.assigned_to}` | {t('inspections.deadline')}: `{a.deadline.strftime('%d %b %Y') if a.deadline else 'N/A'}` | {t('inspections.col_status')}: `{a.status}`")
                with col2:
                    if st.button(t("inspections.mark_done"), key=f"ca_{a.id}"):
                        a.status = "Completed"
                        a.completed_at = datetime.utcnow()
                        db.commit()
                        st.rerun()
                st.divider()
        else:
            st.info(t("inspections.no_pending"))

    db.close()
