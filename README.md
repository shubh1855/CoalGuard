# CoalGuard

AI-Enabled Governance Platform for Coal Mining — WIET Hackverse 2.0

## Quick Start

### 1. Install uv (if not already installed)
```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

### 2. Clone and set up environment
```bash
cd ~/Projects/CoalGuard
uv venv                  # creates .venv with the right Python
uv pip install -e .      # installs all core dependencies
```

### 3. Install PyTorch (choose one)

**GPU (CUDA 12.1):**
```bash
uv pip install torch torchvision --index-url https://download.pytorch.org/whl/cu121
```

**CPU only:**
```bash
uv pip install torch torchvision --index-url https://download.pytorch.org/whl/cpu
```

### 4. Seed demo data and run
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
# Optional — for email alerts (SafeSight alerter)
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=you@gmail.com
SMTP_PASS=your_app_password
ALERT_TO=recipient@example.com
ALERT_ZONE_THRESHOLD=3
ALERT_COOLDOWN_SECONDS=60
```

## Planned Extensions

- OCR upload for digitizing paper records
- Environmental monitoring with IoT sensor feed
- Multilingual interface (Hindi support)
- PostgreSQL + multi-tenant cloud deployment
