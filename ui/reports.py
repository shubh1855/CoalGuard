# ui/reports.py
import streamlit as st
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
from database import SessionLocal, Site, ComplianceItem, Inspection, Violation
from modules.report_gen import generate_site_report


def render():
    st.subheader("Statutory Report Generation")
    db = SessionLocal()
    sites = db.query(Site).all()

    if not sites:
        st.warning("No sites found. Run seed.py first.")
        db.close()
        return

    site_name = st.selectbox("Select Mine Site", [s.name for s in sites])
    site = next(s for s in sites if s.name == site_name)

    st.markdown(f"Generating report for **{site.name}** ({site.subsidiary})")

    compliance_items = db.query(ComplianceItem).filter(ComplianceItem.site_id == site.id).all()
    inspections = db.query(Inspection).filter(Inspection.site_id == site.id).all()
    violations = db.query(Violation).filter(Violation.site_id == site.id).all()

    col1, col2, col3 = st.columns(3)
    col1.metric("Compliance Items", len(compliance_items))
    col2.metric("Inspections", len(inspections))
    col3.metric("CV Violations", len(violations))

    if st.button("Generate PDF Report"):
        pdf = generate_site_report(site, compliance_items, inspections, violations)
        st.download_button(
            label="Download Report PDF",
            data=pdf,
            file_name=f"SafeSight_{site.name.replace(' ', '_')}_report.pdf",
            mime="application/pdf",
        )

    db.close()
