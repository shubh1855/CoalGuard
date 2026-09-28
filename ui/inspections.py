# ui/inspections.py
import streamlit as st
import pandas as pd
from datetime import datetime
import os
import sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
from database import SessionLocal, Inspection, CorrectiveAction, Site, AlertLog


def render():
    st.subheader("Inspection Management")

    db = SessionLocal()
    sites = db.query(Site).all()
    site_map = {s.id: s.name for s in sites}

    tab1, tab2, tab3 = st.tabs(["All Inspections", "Log New Inspection", "Corrective Actions"])

    with tab1:
        inspections = db.query(Inspection).order_by(Inspection.date.desc()).all()
        if inspections:
            df = pd.DataFrame([{
                "ID": i.id,
                "Site": site_map.get(i.site_id, "Unknown"),
                "Type": i.inspection_type,
                "Inspector": i.inspector_name,
                "Date": i.date.strftime("%d %b %Y %H:%M"),
                "Severity": i.severity,
                "Status": i.status,
                "Observations": (i.observations[:80] + "...") if i.observations and len(i.observations) > 80 else i.observations,
            } for i in inspections])

            def style_severity(val):
                m = {"Low": "color: #4ade80", "Medium": "color: #facc15",
                     "High": "color: #fb923c", "Critical": "color: #f87171; font-weight: bold"}
                return m.get(val, "")

            st.dataframe(df.style.map(style_severity, subset=["Severity"]), width='stretch', height=400)

            selected_id = st.number_input("Enter Inspection ID to view corrective actions", min_value=1, step=1)
            if st.button("View Actions"):
                actions = db.query(CorrectiveAction).filter(CorrectiveAction.inspection_id == selected_id).all()
                if actions:
                    for a in actions:
                        st.markdown(f"**Action:** {a.description}")
                        st.markdown(f"Assigned to: `{a.assigned_to}` | Deadline: `{a.deadline.strftime('%d %b %Y') if a.deadline else 'N/A'}` | Status: `{a.status}`")
                        st.divider()
                else:
                    st.info("No corrective actions for this inspection.")
        else:
            st.info("No inspections logged yet.")

    with tab2:
        st.markdown("#### Log Field Inspection")
        col1, col2 = st.columns(2)
        with col1:
            site_name = st.selectbox("Site", [s.name for s in sites])
            inspector = st.text_input("Inspector Name")
            insp_type = st.selectbox("Inspection Type", ["Safety", "Environmental", "Labour"])
            severity = st.selectbox("Severity", ["Low", "Medium", "High", "Critical"])
        with col2:
            lat = st.number_input("Latitude (GPS)", value=23.75, format="%.6f")
            lon = st.number_input("Longitude (GPS)", value=86.42, format="%.6f")
            status = st.selectbox("Status", ["Open", "Action Pending", "Closed"])
            image = st.file_uploader("Attach Photo (optional)", type=["jpg", "png"])

        observations = st.text_area("Observations")

        st.markdown("#### Corrective Action")
        ca_desc = st.text_input("Corrective Action Description")
        ca_assigned = st.text_input("Assign To")
        ca_deadline = st.date_input("Deadline")

        if st.button("Submit Inspection"):
            site_id = next(s.id for s in sites if s.name == site_name)
            img_path = None
            if image:
                os.makedirs("evidence", exist_ok=True)
                img_path = f"evidence/insp_{datetime.utcnow().timestamp()}.jpg"
                with open(img_path, "wb") as f:
                    f.write(image.read())

            insp = Inspection(
                site_id=site_id,
                inspector_name=inspector,
                inspection_type=insp_type,
                latitude=lat,
                longitude=lon,
                observations=observations,
                status=status,
                severity=severity,
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
            if severity in ["High", "Critical"]:
                db.add(AlertLog(
                    site_id=site_id,
                    alert_type="Inspection",
                    message=f"{severity} inspection finding at {site_name}: {observations[:100]}",
                    severity=severity,
                    channel="Dashboard",
                ))
            db.commit()
            st.success("Inspection logged.")
            st.rerun()

    with tab3:
        actions = db.query(CorrectiveAction).filter(CorrectiveAction.status != "Completed").all()
        if actions:
            for a in actions:
                insp = db.query(Inspection).filter(Inspection.id == a.inspection_id).first()
                site_label = site_map.get(insp.site_id, "Unknown") if insp else "Unknown"
                col1, col2 = st.columns([4, 1])
                with col1:
                    st.markdown(f"**{a.description}**  \nSite: `{site_label}` | Assigned: `{a.assigned_to}` | Due: `{a.deadline.strftime('%d %b %Y') if a.deadline else 'N/A'}` | Status: `{a.status}`")
                with col2:
                    if st.button("Mark Done", key=f"ca_{a.id}"):
                        a.status = "Completed"
                        a.completed_at = datetime.utcnow()
                        db.commit()
                        st.rerun()
                st.divider()
        else:
            st.info("No pending corrective actions.")

    db.close()
