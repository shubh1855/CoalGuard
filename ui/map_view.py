# ui/map_view.py — Premium Mine Site Map
import streamlit as st
import folium
from folium.plugins import HeatMap, MarkerCluster, Fullscreen
from streamlit_folium import st_folium
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
from database import SessionLocal, Site, Inspection, Violation, ComplianceItem
from i18n import t as _t

# ──────────────────────────────
# Custom CSS
# ──────────────────────────────
MAP_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');

.map-stats-card {
    background: linear-gradient(135deg, rgba(30,40,60,0.85) 0%, rgba(20,28,45,0.95) 100%);
    border: 1px solid rgba(255,255,255,0.08);
    border-radius: 14px;
    padding: 18px 20px;
    margin-bottom: 12px;
    font-family: 'Inter', sans-serif;
    backdrop-filter: blur(12px);
    transition: border-color 0.2s;
}
.map-stats-card:hover { border-color: rgba(255,255,255,0.15); }
.stat-site-name {
    font-size: 15px;
    font-weight: 600;
    color: #f1f5f9;
    margin-bottom: 10px;
    display: flex;
    align-items: center;
    gap: 8px;
}
.stat-site-sub {
    font-size: 11px;
    color: #64748b;
    font-weight: 500;
    background: rgba(255,255,255,0.06);
    padding: 2px 8px;
    border-radius: 999px;
}
.stat-row {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 5px 0;
    border-bottom: 1px solid rgba(255,255,255,0.04);
}
.stat-row:last-child { border-bottom: none; }
.stat-label { font-size: 12px; color: #94a3b8; }
.stat-value { font-size: 14px; font-weight: 600; }
.stat-value.red    { color: #f87171; }
.stat-value.amber  { color: #fbbf24; }
.stat-value.green  { color: #4ade80; }
.stat-value.blue   { color: #60a5fa; }
.stat-value.purple { color: #a78bfa; }

.legend-box {
    background: rgba(30,40,60,0.85);
    border: 1px solid rgba(255,255,255,0.08);
    border-radius: 12px;
    padding: 14px 18px;
    font-family: 'Inter', sans-serif;
    margin-bottom: 12px;
}
.legend-title {
    font-size: 12px;
    font-weight: 600;
    color: #e2e8f0;
    margin-bottom: 8px;
    text-transform: uppercase;
    letter-spacing: 0.05em;
}
.legend-item {
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 3px 0;
    font-size: 12px;
    color: #94a3b8;
}
.legend-dot {
    width: 10px;
    height: 10px;
    border-radius: 50%;
    flex-shrink: 0;
}

.section-hdr {
    font-family: 'Inter', sans-serif;
    font-size: 15px;
    font-weight: 600;
    color: #e2e8f0;
    letter-spacing: -0.01em;
    margin-bottom: 12px;
    display: flex;
    align-items: center;
    gap: 8px;
}
</style>
"""

# ──────────────────────────────
# Rich popup HTML
# ──────────────────────────────
def _site_popup_html(site, violations_count, overdue_count, inspections_count, compliant_count):
    total_comp = overdue_count + compliant_count
    comp_pct = int(compliant_count / total_comp * 100) if total_comp > 0 else 0
    bar_color = "#22c55e" if comp_pct >= 70 else "#f59e0b" if comp_pct >= 40 else "#ef4444"
    lbl_violations = _t("map.violations")
    lbl_overdue = _t("map.overdue")
    lbl_inspections = _t("map.inspections")
    lbl_compliance = _t("map.compliance")
    return f"""
    <div style="font-family:Inter,sans-serif;min-width:220px;padding:4px">
        <div style="font-size:15px;font-weight:700;color:#1e293b;margin-bottom:2px">{site.name}</div>
        <div style="font-size:11px;color:#64748b;margin-bottom:10px">{site.subsidiary} · {site.location}</div>
        <div style="display:flex;gap:12px;margin-bottom:10px">
            <div style="text-align:center">
                <div style="font-size:20px;font-weight:700;color:#ef4444">{violations_count}</div>
                <div style="font-size:10px;color:#64748b">{lbl_violations}</div>
            </div>
            <div style="text-align:center">
                <div style="font-size:20px;font-weight:700;color:#f59e0b">{overdue_count}</div>
                <div style="font-size:10px;color:#64748b">{lbl_overdue}</div>
            </div>
            <div style="text-align:center">
                <div style="font-size:20px;font-weight:700;color:#3b82f6">{inspections_count}</div>
                <div style="font-size:10px;color:#64748b">{lbl_inspections}</div>
            </div>
        </div>
        <div style="font-size:11px;color:#64748b;margin-bottom:4px">{lbl_compliance} {comp_pct}%</div>
        <div style="background:#e2e8f0;border-radius:999px;height:6px;overflow:hidden">
            <div style="background:{bar_color};width:{comp_pct}%;height:100%;border-radius:999px;transition:width 0.3s"></div>
        </div>
    </div>
    """


# ──────────────────────────────
# Site stats sidebar card
# ──────────────────────────────
def _site_stats_html(site, violations_count, overdue_count, open_insp, critical_count, compliant_count, total_comp):
    comp_pct = int(compliant_count / total_comp * 100) if total_comp > 0 else 0
    return f"""
    <div class="map-stats-card">
        <div class="stat-site-name">
            ⛏️ {site.name}
            <span class="stat-site-sub">{site.subsidiary}</span>
        </div>
        <div class="stat-row">
            <span class="stat-label">{_t("map.cv_violations")}</span>
            <span class="stat-value red">{violations_count}</span>
        </div>
        <div class="stat-row">
            <span class="stat-label">{_t("map.overdue_compliance")}</span>
            <span class="stat-value amber">{overdue_count}</span>
        </div>
        <div class="stat-row">
            <span class="stat-label">{_t("map.compliance_rate")}</span>
            <span class="stat-value green">{comp_pct}%</span>
        </div>
        <div class="stat-row">
            <span class="stat-label">{_t("map.open_inspections")}</span>
            <span class="stat-value blue">{open_insp}</span>
        </div>
        <div class="stat-row">
            <span class="stat-label">{_t("map.critical_findings")}</span>
            <span class="stat-value {'red' if critical_count > 0 else 'green'}">{critical_count}</span>
        </div>
    </div>"""


# ══════════════════════════════
# Main render
# ══════════════════════════════
def render():
    st.markdown(MAP_CSS, unsafe_allow_html=True)
    st.markdown(f'<div class="section-hdr">🗺️ {_t("map.title")}</div>', unsafe_allow_html=True)

    db = SessionLocal()

    try:
        sites = db.query(Site).all()
        all_inspections = db.query(Inspection).all()
        all_violations = db.query(Violation).all()
        all_compliance = db.query(ComplianceItem).all()

        # ── Sidebar Controls ────────────────────────
        lbl_sites = _t("map.layer_sites")
        lbl_inspections = _t("map.layer_inspections")
        lbl_heatmap = _t("map.layer_heatmap")

        col_ctrl1, col_ctrl2 = st.columns(2)
        with col_ctrl1:
            tile_choice = st.selectbox(f"🎨 {_t('map.style')}", [
                "OpenStreetMap",
                "Topographic",
                "Satellite",
            ], index=0)
        with col_ctrl2:
            layers = st.multiselect(f"📍 {_t('map.layers')}", [
                lbl_sites, lbl_inspections, lbl_heatmap,
            ], default=[lbl_sites, lbl_inspections, lbl_heatmap])

        # ── Free tile providers (no API keys needed) ──
        TILE_CONFIGS = {
            "OpenStreetMap": {
                "tiles": "OpenStreetMap",
            },
            "Topographic": {
                "tiles": "https://{s}.tile.opentopomap.org/{z}/{x}/{y}.png",
                "attr": '© <a href="https://opentopomap.org">OpenTopoMap</a> contributors',
            },
            "Satellite": {
                "tiles": "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
                "attr": "Esri, Maxar, Earthstar Geographics",
            },
        }

        # ── Calculate center ────────────────────────
        if sites:
            avg_lat = sum(s.latitude for s in sites if s.latitude) / max(1, len([s for s in sites if s.latitude]))
            avg_lon = sum(s.longitude for s in sites if s.longitude) / max(1, len([s for s in sites if s.longitude]))
        else:
            avg_lat, avg_lon = 22.5, 82.0

        tile_cfg = TILE_CONFIGS.get(tile_choice, TILE_CONFIGS["OpenStreetMap"])
        m = folium.Map(location=[avg_lat, avg_lon], zoom_start=5, **tile_cfg)

        # Add fullscreen control
        Fullscreen(
            position="topleft",
            title="Fullscreen",
            title_cancel="Exit Fullscreen",
        ).add_to(m)

        severity_colors = {
            "Low": "#22c55e", "Medium": "#f59e0b",
            "High": "#ef4444", "Critical": "#dc2626",
        }

        # ── Sites layer ─────────────────────────────
        if lbl_sites in layers:
            for site in sites:
                if not (site.latitude and site.longitude):
                    continue
                v_count = sum(1 for v in all_violations if v.site_id == site.id)
                o_count = sum(1 for c in all_compliance if c.site_id == site.id and c.status == "Overdue")
                c_count = sum(1 for c in all_compliance if c.site_id == site.id and c.status == "Compliant")
                i_count = sum(1 for i in all_inspections if i.site_id == site.id)

                popup_html = _site_popup_html(site, v_count, o_count, i_count, c_count)

                # Pulsing marker effect via DivIcon
                icon_html = f"""
                <div style="position:relative;width:36px;height:36px">
                    <div style="
                        position:absolute;top:50%;left:50%;
                        transform:translate(-50%,-50%);
                        width:16px;height:16px;
                        background:linear-gradient(135deg,#3b82f6,#60a5fa);
                        border-radius:50%;
                        border:3px solid rgba(255,255,255,0.9);
                        box-shadow:0 0 12px rgba(59,130,246,0.5);
                    "></div>
                    <div style="
                        position:absolute;top:50%;left:50%;
                        transform:translate(-50%,-50%);
                        width:36px;height:36px;
                        background:rgba(59,130,246,0.15);
                        border-radius:50%;
                        animation:pulse 2s ease-in-out infinite;
                    "></div>
                </div>
                <style>
                @keyframes pulse {{
                    0%,100% {{ transform:translate(-50%,-50%) scale(1); opacity:0.7; }}
                    50% {{ transform:translate(-50%,-50%) scale(1.3); opacity:0; }}
                }}
                </style>
                """

                folium.Marker(
                    location=[site.latitude, site.longitude],
                    popup=folium.Popup(popup_html, max_width=260),
                    tooltip=f"<b>{site.name}</b> ({site.subsidiary})",
                    icon=folium.DivIcon(
                        html=icon_html,
                        icon_size=(36, 36),
                        icon_anchor=(18, 18),
                    ),
                ).add_to(m)

        # ── Inspections layer (clustered) ───────────
        if lbl_inspections in layers:
            marker_cluster = MarkerCluster(
                name=_t("map.layer_inspections"),
                options={"maxClusterRadius": 40},
            ).add_to(m)

            no_obs = _t("map.no_observations")
            insp_label = _t("map.inspection_label")

            for insp in all_inspections:
                if not (insp.latitude and insp.longitude):
                    continue
                color = severity_colors.get(insp.severity, "#64748b")
                site_name = next((s.name for s in sites if s.id == insp.site_id), "Unknown")
                popup = f"""
                <div style="font-family:Inter,sans-serif;min-width:180px">
                    <div style="font-weight:600;color:#1e293b;margin-bottom:4px">{insp.inspection_type} {insp_label}</div>
                    <div style="font-size:11px;color:#64748b;margin-bottom:6px">{site_name}</div>
                    <div style="display:flex;gap:6px;align-items:center;margin-bottom:4px">
                        <span style="
                            background:{color};color:#fff;
                            padding:2px 8px;border-radius:999px;
                            font-size:10px;font-weight:600;
                        ">{insp.severity}</span>
                        <span style="font-size:11px;color:#475569">{insp.status}</span>
                    </div>
                    <div style="font-size:11px;color:#475569;line-height:1.4">{insp.observations or no_obs}</div>
                    <div style="font-size:10px;color:#94a3b8;margin-top:4px">{insp.date.strftime('%d %b %Y') if insp.date else ''}</div>
                </div>
                """
                folium.CircleMarker(
                    location=[insp.latitude, insp.longitude],
                    radius=7,
                    color=color,
                    fill=True,
                    fill_color=color,
                    fill_opacity=0.8,
                    weight=2,
                    popup=folium.Popup(popup, max_width=220),
                    tooltip=f"{insp.severity} — {insp.inspection_type}",
                ).add_to(marker_cluster)

        # ── Violation heatmap layer ─────────────────
        if lbl_heatmap in layers:
            heat_data = []
            for v in all_violations:
                site = next((s for s in sites if s.id == v.site_id), None)
                if site and site.latitude and site.longitude:
                    import random
                    lat = site.latitude + random.uniform(-0.02, 0.02)
                    lon = site.longitude + random.uniform(-0.02, 0.02)
                    heat_data.append([lat, lon, 1])

            if heat_data:
                HeatMap(
                    heat_data,
                    name=_t("map.layer_heatmap"),
                    radius=25,
                    blur=15,
                    max_zoom=10,
                    gradient={
                        "0.2": "#3b82f6",
                        "0.4": "#22c55e",
                        "0.6": "#f59e0b",
                        "0.8": "#ef4444",
                        "1.0": "#dc2626",
                    },
                ).add_to(m)

        # Add layer control
        folium.LayerControl(collapsed=False).add_to(m)

        # ── Layout: Map + Stats Sidebar ─────────────
        map_col, stats_col = st.columns([3, 1])

        with map_col:
            st_folium(m, width=None, height=560, returned_objects=[])

        with stats_col:
            # Legend
            legend_html = f"""
            <div class="legend-box">
                <div class="legend-title">{_t("map.legend")}</div>
                <div class="legend-item">
                    <div class="legend-dot" style="background:linear-gradient(135deg,#3b82f6,#60a5fa);box-shadow:0 0 6px rgba(59,130,246,0.4)"></div>
                    {_t("map.legend_site")}
                </div>
                <div class="legend-item">
                    <div class="legend-dot" style="background:#22c55e"></div>
                    {_t("map.legend_low")}
                </div>
                <div class="legend-item">
                    <div class="legend-dot" style="background:#f59e0b"></div>
                    {_t("map.legend_medium")}
                </div>
                <div class="legend-item">
                    <div class="legend-dot" style="background:#ef4444"></div>
                    {_t("map.legend_high")}
                </div>
                <div class="legend-item">
                    <div class="legend-dot" style="background:#dc2626"></div>
                    {_t("map.legend_critical")}
                </div>
            </div>
            """
            st.markdown(legend_html, unsafe_allow_html=True)

            # Per-site stats
            st.markdown(f'<div class="legend-title" style="margin-top:8px">{_t("map.site_details")}</div>', unsafe_allow_html=True)
            for site in sites:
                v_count = sum(1 for v in all_violations if v.site_id == site.id)
                o_count = sum(1 for c in all_compliance if c.site_id == site.id and c.status == "Overdue")
                c_count = sum(1 for c in all_compliance if c.site_id == site.id and c.status == "Compliant")
                t_count = sum(1 for c in all_compliance if c.site_id == site.id)
                open_insp = sum(1 for i in all_inspections if i.site_id == site.id and i.status in ("Open", "Action Pending"))
                crit_count = sum(1 for i in all_inspections if i.site_id == site.id and i.severity == "Critical")

                st.markdown(
                    _site_stats_html(site, v_count, o_count, open_insp, crit_count, c_count, t_count),
                    unsafe_allow_html=True,
                )

    finally:
        db.close()
