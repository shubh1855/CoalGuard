# ui/dashboard.py — Premium SafeSight Dashboard
import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
from database import SessionLocal, Site, Violation, ComplianceItem, Inspection, AlertLog
from i18n import t

# ──────────────────────────────────────────────
# Custom CSS
# ──────────────────────────────────────────────
DASHBOARD_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');

/* Alert cards */
.alert-card {
    background: rgba(30,40,60,0.6);
    border: 1px solid rgba(255,255,255,0.06);
    border-radius: 12px;
    padding: 14px 16px;
    margin-bottom: 10px;
    font-family: 'Inter', sans-serif;
    transition: border-color 0.2s;
}
.alert-card:hover { border-color: rgba(255,255,255,0.15); }
.alert-badge {
    font-size: 10px;
    font-weight: 600;
    padding: 2px 8px;
    border-radius: 999px;
    text-transform: uppercase;
    letter-spacing: 0.05em;
}
.alert-badge.high     { background: rgba(239,68,68,0.2); color: #f87171; }
.alert-badge.critical { background: rgba(239,68,68,0.3); color: #fca5a5; }
.alert-badge.medium   { background: rgba(245,158,11,0.2); color: #fbbf24; }
.alert-badge.low      { background: rgba(34,197,94,0.2); color: #4ade80; }
.alert-msg  { color: #cbd5e1; font-size: 13px; margin-top: 6px; line-height: 1.4; }
.alert-time { color: #64748b; font-size: 11px; margin-top: 4px; }
</style>
"""

# ──────────────────────────────────
# Plotly default dark layout
# ──────────────────────────────────
PLOTLY_LAYOUT = dict(
    template="plotly_dark",
    paper_bgcolor="rgba(0,0,0,0)",
    plot_bgcolor="rgba(0,0,0,0)",
    font=dict(family="Inter, sans-serif", size=12, color="#94a3b8"),
    margin=dict(l=40, r=20, t=36, b=40),
    legend=dict(
        bgcolor="rgba(0,0,0,0)",
        font=dict(size=11, color="#94a3b8"),
    ),
)


def _alert_card(alert):
    sev = (alert.severity or "medium").lower()
    badge_cls = sev if sev in ("high", "critical", "medium", "low") else "medium"
    icon = {"high": "🔴", "critical": "🚨", "medium": "🟡", "low": "🟢"}.get(sev, "⚪")
    ts = alert.sent_at.strftime("%d %b %Y • %H:%M") if alert.sent_at else ""
    return f"""
    <div class="alert-card">
        <span class="alert-badge {badge_cls}">{icon} {alert.alert_type}</span>
        <div class="alert-msg">{alert.message}</div>
        <div class="alert-time">{ts}</div>
    </div>"""


# ═══════════════════════════════════
# Main render
# ═══════════════════════════════════
def render():
    st.markdown(DASHBOARD_CSS, unsafe_allow_html=True)

    db = SessionLocal()

    try:
        sites = db.query(Site).all()
        site_names = {s.id: s.name for s in sites}

        # ── Global site filter ──────────────────────
        site_options = [t("dashboard.all_sites")] + [s.name for s in sites]
        selected_site = st.selectbox(
            f"🔍 {t('dashboard.filter_site')}", site_options,
            index=0, key="dash_site_filter"
        )
        site_id_filter = None
        if selected_site != t("dashboard.all_sites"):
            site_id_filter = next(s.id for s in sites if s.name == selected_site)

        # ── Query data ──────────────────────────────
        viol_q = db.query(Violation)
        comp_q = db.query(ComplianceItem)
        insp_q = db.query(Inspection)
        alert_q = db.query(AlertLog).order_by(AlertLog.sent_at.desc())
        if site_id_filter:
            viol_q = viol_q.filter(Violation.site_id == site_id_filter)
            comp_q = comp_q.filter(ComplianceItem.site_id == site_id_filter)
            insp_q = insp_q.filter(Inspection.site_id == site_id_filter)
            alert_q = alert_q.filter(AlertLog.site_id == site_id_filter)

        violations = viol_q.all()
        compliance_items = comp_q.all()
        inspections = insp_q.all()
        alerts = alert_q.limit(15).all()

        # ── KPI calculations ────────────────────────
        n_sites = len(sites) if not site_id_filter else 1
        n_violations = len(violations)
        n_overdue = sum(1 for c in compliance_items if c.status == "Overdue")
        n_open_insp = sum(1 for i in inspections if i.status in ("Open", "Action Pending"))
        n_critical = sum(1 for i in inspections if i.severity == "Critical")

        # ── KPI Row ─────────────────────────────────
        st.subheader(f"📊 {t('dashboard.overview')}")
        c1, c2, c3, c4, c5 = st.columns(5)
        with c1:
            st.metric(t('dashboard.active_sites'), n_sites)
        with c2:
            st.metric(f"🚨 {t('dashboard.cv_violations')}", n_violations,
                      delta=f"+{n_violations}" if n_violations > 0 else None,
                      delta_color="inverse")
        with c3:
            st.metric(f"⏰ {t('dashboard.overdue_compliance')}", n_overdue,
                      delta=f"-{n_overdue}" if n_overdue > 0 else None,
                      delta_color="inverse")
        with c4:
            st.metric(f"🔍 {t('dashboard.open_inspections')}", n_open_insp)
        with c5:
            st.metric(f"⚠️ {t('dashboard.critical_findings')}", n_critical,
                      delta=f"+{n_critical}" if n_critical > 0 else None,
                      delta_color="inverse")

        st.divider()

        # ── Row 1: Compliance Donut + Violations by Type ──
        col_l, col_r = st.columns(2)

        with col_l:
            st.markdown(f"**🛡️ {t('dashboard.compliance_status')}**")
            if compliance_items:
                status_counts = pd.DataFrame(
                    [{"Status": c.status} for c in compliance_items]
                )["Status"].value_counts().reset_index()
                status_counts.columns = ["Status", "Count"]

                color_map = {
                    "Compliant": "#22c55e", "Pending": "#f59e0b",
                    "Overdue": "#ef4444", "In Progress": "#3b82f6"
                }
                fig = px.pie(
                    status_counts, names="Status", values="Count",
                    hole=0.55,
                    color="Status",
                    color_discrete_map=color_map,
                )
                fig.update_traces(
                    textposition="outside", textinfo="label+percent",
                    textfont_size=12,
                    marker=dict(line=dict(color="rgba(0,0,0,0.3)", width=2)),
                    pull=[0.03] * len(status_counts),
                )
                fig.update_layout(**PLOTLY_LAYOUT, height=340, showlegend=False)
                total_comp = status_counts["Count"].sum()
                compliant_count = status_counts.loc[status_counts["Status"] == "Compliant", "Count"]
                pct = int(compliant_count.values[0] / total_comp * 100) if len(compliant_count) > 0 else 0
                fig.add_annotation(
                    text=f"<b style='font-size:28px;color:#f1f5f9'>{pct}%</b><br>"
                         f"<span style='font-size:11px;color:#64748b'>{t('dashboard.compliant')}</span>",
                    showarrow=False, font=dict(size=14),
                )
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.info(t("dashboard.no_compliance"))

        with col_r:
            st.markdown(f"**🦺 {t('dashboard.violations_by_type')}**")
            if violations:
                vtype_df = pd.DataFrame(
                    [{"Type": v.violation_type} for v in violations]
                )["Type"].value_counts().reset_index()
                vtype_df.columns = ["Type", "Count"]

                type_colors = {
                    "NO-Hardhat": "#ef4444", "NO-Vest": "#f59e0b",
                    "Zone Intrusion": "#8b5cf6", "NO-Gloves": "#3b82f6",
                }
                colors = [type_colors.get(t_val, "#64748b") for t_val in vtype_df["Type"]]

                fig2 = go.Figure(go.Bar(
                    x=vtype_df["Count"], y=vtype_df["Type"],
                    orientation="h",
                    marker=dict(color=colors, line=dict(width=0), cornerradius=6),
                    text=vtype_df["Count"],
                    textposition="outside",
                    textfont=dict(color="#e2e8f0", size=12),
                ))
                fig2.update_layout(
                    **PLOTLY_LAYOUT, height=340,
                    yaxis=dict(autorange="reversed"),
                    xaxis=dict(showgrid=False, zeroline=False),
                )
                st.plotly_chart(fig2, use_container_width=True)
            else:
                st.info(t("dashboard.no_violations"))

        st.divider()

        # ── Row 2: Violations Timeline ──
        st.markdown(f"**📈 {t('dashboard.violations_timeline')}**")
        if violations:
            viol_df = pd.DataFrame([{
                "timestamp": v.timestamp,
                "type": v.violation_type,
                "site": site_names.get(v.site_id, "Unknown"),
            } for v in violations])
            viol_df["date"] = pd.to_datetime(viol_df["timestamp"]).dt.date
            daily = viol_df.groupby(["date", "site"]).size().reset_index(name="count")

            site_colors = {}
            palette = ["#3b82f6", "#f59e0b", "#22c55e", "#8b5cf6", "#ef4444", "#ec4899"]
            for idx, s in enumerate(daily["site"].unique()):
                site_colors[s] = palette[idx % len(palette)]

            fig3 = px.area(
                daily, x="date", y="count", color="site",
                color_discrete_map=site_colors,
                labels={"date": t("dashboard.date"), "count": t("dashboard.violations"), "site": t("dashboard.site")},
            )
            fig3.update_traces(line=dict(width=2))
            for trace in fig3.data:
                hex_color = trace.line.color or "#3b82f6"
                if "rgb" in (hex_color or ""):
                    trace.fillcolor = hex_color.replace("rgb", "rgba").replace(")", ",0.15)")
                else:
                    trace.fillcolor = hex_color + "26"
            fig3.update_layout(
                **PLOTLY_LAYOUT, height=300,
                xaxis=dict(showgrid=False),
                yaxis=dict(showgrid=True, gridcolor="rgba(148,163,184,0.08)"),
                hovermode="x unified",
            )
            st.plotly_chart(fig3, use_container_width=True)
        else:
            st.info(t("dashboard.no_violations_chart"))

        st.divider()

        # ── Row 3: Inspection Severity + Alert Feed ──
        col_left, col_right = st.columns([3, 2])

        with col_left:
            st.markdown(f"**🔬 {t('dashboard.inspection_severity')}**")
            if inspections:
                sev_df = pd.DataFrame([{
                    "Severity": i.severity,
                    "Site": site_names.get(i.site_id, "Unknown"),
                } for i in inspections])
                sev_grouped = sev_df.groupby(["Site", "Severity"]).size().reset_index(name="Count")

                sev_colors = {
                    "Low": "#22c55e", "Medium": "#f59e0b",
                    "High": "#ef4444", "Critical": "#dc2626",
                }
                fig4 = px.bar(
                    sev_grouped, x="Site", y="Count", color="Severity",
                    barmode="group",
                    color_discrete_map=sev_colors,
                    category_orders={"Severity": ["Low", "Medium", "High", "Critical"]},
                )
                fig4.update_traces(marker=dict(cornerradius=5))
                fig4.update_layout(
                    **PLOTLY_LAYOUT, height=340,
                    xaxis=dict(showgrid=False),
                    yaxis=dict(showgrid=True, gridcolor="rgba(148,163,184,0.08)"),
                )
                st.plotly_chart(fig4, use_container_width=True)
            else:
                st.info(t("dashboard.no_inspections"))

        with col_right:
            st.markdown(f"**🔔 {t('dashboard.recent_alerts')}**")
            if alerts:
                alerts_html = ""
                for a in alerts[:8]:
                    alerts_html += _alert_card(a)
                st.markdown(
                    f'<div style="max-height:380px;overflow-y:auto;padding-right:4px">{alerts_html}</div>',
                    unsafe_allow_html=True,
                )
            else:
                st.info(t("dashboard.no_alerts"))

        st.divider()

        # ── Row 4: Site comparison ──
        if not site_id_filter and len(sites) > 1:
            st.markdown(f"**🏭 {t('dashboard.site_comparison')}**")

            all_violations = db.query(Violation).all()
            all_compliance = db.query(ComplianceItem).all()
            all_inspections = db.query(Inspection).all()

            comparison_data = []
            for s in sites:
                sv = sum(1 for v in all_violations if v.site_id == s.id)
                so = sum(1 for c in all_compliance if c.site_id == s.id and c.status == "Overdue")
                sc = sum(1 for c in all_compliance if c.site_id == s.id and c.status == "Compliant")
                si = sum(1 for i in all_inspections if i.site_id == s.id and i.status in ("Open", "Action Pending"))
                scrit = sum(1 for i in all_inspections if i.site_id == s.id and i.severity == "Critical")
                comparison_data.append({
                    "Site": s.name,
                    t("dashboard.violations"): sv,
                    t("dashboard.overdue"): so,
                    t("dashboard.compliant"): sc,
                    t("dashboard.open_inspections"): si,
                    t("dashboard.critical_findings"): scrit,
                })

            comp_df = pd.DataFrame(comparison_data)
            metrics = [t("dashboard.violations"), t("dashboard.overdue"),
                       t("dashboard.compliant"), t("dashboard.open_inspections"),
                       t("dashboard.critical_findings")]
            met_colors = ["#ef4444", "#f59e0b", "#22c55e", "#8b5cf6", "#dc2626"]

            fig5 = go.Figure()
            for i, metric in enumerate(metrics):
                fig5.add_trace(go.Bar(
                    name=metric,
                    x=comp_df["Site"],
                    y=comp_df[metric],
                    marker_color=met_colors[i],
                    marker=dict(cornerradius=5),
                ))
            fig5.update_layout(
                **PLOTLY_LAYOUT, height=340,
                barmode="group",
                xaxis=dict(showgrid=False),
                yaxis=dict(showgrid=True, gridcolor="rgba(148,163,184,0.08)"),
            )
            st.plotly_chart(fig5, use_container_width=True)

    finally:
        db.close()
