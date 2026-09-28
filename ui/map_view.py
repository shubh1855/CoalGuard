# ui/map_view.py
import streamlit as st
import folium
from streamlit_folium import st_folium
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
from database import SessionLocal, Site, Inspection, Violation


def render():
    st.subheader("Mine Site Map")
    db = SessionLocal()
    sites = db.query(Site).all()
    inspections = db.query(Inspection).all()

    m = folium.Map(location=[22.5, 82.0], zoom_start=5, tiles="OpenStreetMap")

    severity_colors = {"Low": "green", "Medium": "orange", "High": "red", "Critical": "darkred"}

    for site in sites:
        if site.latitude and site.longitude:
            violations_count = db.query(Violation).filter(Violation.site_id == site.id).count()
            overdue_count = sum(1 for c in site.compliance_items if c.status == "Overdue")
            popup_html = f"""
            <b>{site.name}</b><br>
            Subsidiary: {site.subsidiary}<br>
            Location: {site.location}<br>
            CV Violations: {violations_count}<br>
            Overdue Compliance: {overdue_count}
            """
            folium.CircleMarker(
                location=[site.latitude, site.longitude],
                radius=14,
                color="#60a5fa",
                fill=True,
                fill_color="#1e3a5f",
                fill_opacity=0.9,
                popup=folium.Popup(popup_html, max_width=200),
                tooltip=site.name,
            ).add_to(m)

    for insp in inspections:
        if insp.latitude and insp.longitude:
            color = severity_colors.get(insp.severity, "gray")
            folium.CircleMarker(
                location=[insp.latitude, insp.longitude],
                radius=6,
                color=color,
                fill=True,
                fill_opacity=0.8,
                tooltip=f"Inspection: {insp.severity} — {insp.inspection_type}",
            ).add_to(m)

    st_folium(m, width=None, height=500)

    st.caption("Blue circles: mine sites. Colored dots: inspection findings (green=Low, orange=Medium, red=High, dark red=Critical)")
    db.close()
