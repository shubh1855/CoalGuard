# ui/reports.py
import streamlit as st
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
from database import SessionLocal, Site, ComplianceItem, Inspection, Violation
from modules.report_gen import generate_site_report
from i18n import t


def render():
    st.subheader(t("reports.title"))
    db = SessionLocal()
    sites = db.query(Site).all()

    if not sites:
        st.warning(t("reports.no_sites"))
        db.close()
        return

    site_name = st.selectbox(t("reports.select_site"), [s.name for s in sites])
    site = next(s for s in sites if s.name == site_name)

    st.markdown(t("reports.generating_for", name=site.name, subsidiary=site.subsidiary))

    compliance_items = db.query(ComplianceItem).filter(ComplianceItem.site_id == site.id).all()
    inspections = db.query(Inspection).filter(Inspection.site_id == site.id).all()
    violations = db.query(Violation).filter(Violation.site_id == site.id).all()

    col1, col2, col3 = st.columns(3)
    col1.metric(t("reports.compliance_items"), len(compliance_items))
    col2.metric(t("reports.inspections"), len(inspections))
    col3.metric(t("reports.cv_violations"), len(violations))

    if st.button(t("reports.generate_btn")):
        pdf = generate_site_report(site, compliance_items, inspections, violations)
        st.download_button(
            label=t("reports.download_btn"),
            data=pdf,
            file_name=f"SafeSight_{site.name.replace(' ', '_')}_report.pdf",
            mime="application/pdf",
        )

    db.close()
