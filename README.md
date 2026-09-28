# CoalGuard

AI-Enabled Governance Platform for Coal Mining — WIET Hackverse 2.0

## Quick Start

### 1. Install uv
```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

### 2. Sync Environment and Dependencies
CoalGuard uses a modern `uv.lock` file. You do not need to create a venv manually; `uv` handles it automatically.
```bash
cd ~/Projects/CoalGuard
uv sync
```
*(Note: If you have a GPU, you can customize the torch installation by running `uv pip install torch torchvision --index-url https://download.pytorch.org/whl/cu121` afterwards)*

### 3. Seed demo data and run
```bash
uv run python seed.py
uv run streamlit run app.py
```

Open http://localhost:8501

---

## Project Structure

```
CoalGuard/
├── app.py                  # Streamlit entry point
├── database.py             # SQLAlchemy ORM (Site, Compliance, Inspection, Violation, Alert)
├── seed.py                 # Demo data seed (3 Indian coal mine sites)
├── pyproject.toml          # Dependencies (uv/pip compatible)
├── uv.lock                 # Strict dependency lockfile
├── modules/
│   ├── detector.py         # YOLOv8 PPE detector (from SafeSight)
│   ├── tracked_detector.py # DeepSORT tracked detector
│   ├── zone_detector.py    # Restricted zone detection
│   ├── violation_logger.py # CSV + DB violation logging
│   ├── alerts.py           # Email/voice alerting
│   └── report_gen.py       # ReportLab PDF generator
└── ui/
    ├── dashboard.py        # KPI metrics, charts, alerts
    ├── compliance.py       # Statutory compliance tracker
    ├── inspections.py      # Field inspection management
    ├── map_view.py         # Folium mine site map
    ├── live_monitor.py     # Live CV safety monitor
    └── reports.py          # PDF report download
```

## Pages

| Page | What it does |
|------|-------------|
| Dashboard | 5 KPI metrics, compliance chart, alert feed, violations timeline |
| Live Safety Monitor | Real-time YOLOv8 PPE detection via webcam or uploaded video |
| Compliance Tracker | Filter/update statutory compliance items per mine site |
| Inspection Management | Log field inspections, corrective actions, photo upload |
| Mine Site Map | Folium map with site markers and inspection severity dots |
| Reports | Generate and download PDF governance report per site |

## Environment Variables

Create `.env` in project root:
```env
# Optional — for email alerts
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=you@gmail.com
SMTP_PASS=your_app_password
ALERT_TO=recipient@example.com
ALERT_ZONE_THRESHOLD=3
ALERT_COOLDOWN_SECONDS=60
```

## Planned Features & UI Enhancements

**Core Extensions:**
- Environmental monitoring with live IoT sensor feeds (Air quality, dust, gas)
- Multilingual interface (Hindi support via i18n JSON)
- PostgreSQL + multi-tenant architecture for cloud deployment

**Rich UI Upgrades:**
- **Streamlit-AgGrid:** Replace basic dataframes in Compliance/Inspections with AgGrid to support grouping, advanced filtering, and instant Excel exports.
- **Plotly & Echarts:** Transition from Altair to Plotly/Echarts for 3D interactive site scatter plots, animated timelines, and live IoT gauge widgets in the Dashboard.
- **Cross-Filtering:** Enable clicking a specific site on the Folium Map to instantly cross-filter the KPIs and charts on the Dashboard.
