# SafeSight

AI-Enabled Industrial Safety Governance Platform

## Quick Start

### 1. Install uv
```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

### 2. Sync Environment and Dependencies
SafeSight uses a modern `uv.lock` file. You do not need to create a venv manually; `uv` handles it automatically.
```bash
cd ~/Projects/SafeSight
uv sync
```
*(Note: If you have a GPU, you can customize the torch installation by running `uv pip install torch torchvision --index-url https://download.pytorch.org/whl/cu121` afterwards)*

### 3. Set Up the Database

SafeSight supports **PostgreSQL** (recommended) and **SQLite** (zero-config fallback).

**Option A — PostgreSQL via Docker (recommended):**
```bash
docker run -d \
  --name safesight-pg \
  -e POSTGRES_USER=postgres \
  -e POSTGRES_PASSWORD=postgres \
  -e POSTGRES_DB=safesight \
  -p 5432:5432 \
  postgres:16-alpine
```

Then set in your `.env`:
```env
DATABASE_URL=postgresql+psycopg2://postgres:postgres@localhost:5432/safesight
```

**Option B — PostgreSQL (native install):**
```sql
CREATE DATABASE safesight;
```

**Option C — SQLite (no setup needed):**
```env
DATABASE_URL=sqlite:///SafeSight.db
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
SafeSight/
├── app.py                  # Streamlit entry point (+ language selector)
├── database.py             # SQLAlchemy ORM (PostgreSQL/SQLite, env-driven)
├── i18n.py                 # Internationalization helper (JSON locale loader)
├── seed.py                 # Demo data seed (3 industrial safety sites)
├── pyproject.toml          # Dependencies (uv/pip compatible)
├── uv.lock                 # Strict dependency lockfile
├── .env                    # DATABASE_URL + SMTP config (not committed)
├── .env.example            # Template for .env
├── assets/
│   ├── icon.svg            # Modern SafeSight app icon (auto-adapts to dark mode)
│   └── logo.svg            # Modern SafeSight full logo (auto-adapts to dark mode)
├── locales/
│   ├── en.json             # English translations (default)
│   └── hi.json             # Hindi (हिन्दी) translations
├── modules/
│   ├── detector.py         # YOLOv8 PPE detector (from SafeSight)
│   ├── tracked_detector.py # DeepSORT tracked detector
│   ├── zone_detector.py    # Restricted zone detection
│   ├── violation_logger.py # CSV + DB violation logging
│   ├── alerts.py           # Email/voice alerting
│   └── report_gen.py       # ReportLab PDF generator
└── ui/
    ├── dashboard.py        # KPI metrics, Plotly charts, alerts, site comparison
    ├── compliance.py       # Statutory compliance tracker
    ├── inspections.py      # Field inspection management
    ├── map_view.py         # Folium map with heatmap, clusters, layer controls
    ├── live_monitor.py     # Live CV safety monitor
    └── reports.py          # PDF report download
```

## Pages

| Page | What it does |
| ---- | ------------ |
| **Dashboard** | 5 KPI metrics with deltas, Plotly donut (compliance), horizontal bar (violation types), area chart (timeline by site), grouped bar (severity by site), styled alert feed, site comparison chart. Global site filter. |
| **Live Safety Monitor** | Real-time YOLOv8 PPE detection via webcam or uploaded video |
| **Compliance Tracker** | Filter/update statutory compliance items per mine site |
| **Inspection Management** | Log field inspections, corrective actions, photo upload |
| **Mine Site Map** | Folium map with tile switcher (OpenStreetMap/Topographic/Satellite), layer toggles (Sites/Inspections/Heatmap), pulsing DivIcon markers, MarkerCluster for inspections, violation density HeatMap, rich HTML popups with compliance bars, color legend, per-site stats sidebar, fullscreen mode |
| **Reports** | Generate and download PDF governance report per site |

## Database

SafeSight connects to the database specified by the `DATABASE_URL` environment variable.

| Backend | `DATABASE_URL` | Notes |
| ------- | -------------- | ----- |
| **PostgreSQL** (recommended) | `postgresql+psycopg2://postgres:postgres@localhost:5432/safesight` | Production-ready |
| SQLite (fallback) | `sqlite:///SafeSight.db` | Zero-config, single file |

The database driver for PostgreSQL is `psycopg2-binary` (included in dependencies — no C build tools needed).

### ORM Models

| Model | Table | Key fields |
| ----- | ----- | ---------- |
| `Site` | `sites` | name, location, lat/lon, subsidiary |
| `ComplianceItem` | `compliance_items` | site_id, category, regulation, status, due_date |
| `Inspection` | `inspections` | site_id, inspector, type, severity, status, lat/lon |
| `CorrectiveAction` | `corrective_actions` | inspection_id, description, assigned_to, deadline |
| `Violation` | `violations` | site_id, worker_id, violation_type, source, resolved |
| `AlertLog` | `alert_log` | site_id, alert_type, message, severity, channel |
| `Contractor` | `contractors` | site_id, name, license_number, compliance_status |

## Environment Variables

Create `.env` in project root (see `.env.example`):
```env
# --- Database ---
DATABASE_URL=postgresql+psycopg2://postgres:postgres@localhost:5432/safesight

# --- Email Alerts (optional) ---
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=you@gmail.com
SMTP_PASS=your_app_password
ALERT_TO=recipient@example.com
ALERT_ZONE_THRESHOLD=3
ALERT_COOLDOWN_SECONDS=60
```

## Key Dependencies

| Package | Purpose |
| ------- | ------- |
| `streamlit` | Web UI framework |
| `sqlalchemy` + `psycopg2-binary` | ORM + PostgreSQL driver |
| `plotly` | Interactive dashboard charts (donut, bar, area, grouped) |
| `folium` + `streamlit-folium` | Map with HeatMap, MarkerCluster, Fullscreen plugins |
| `ultralytics` + `opencv-python` | YOLOv8 PPE detection |
| `deep-sort-realtime` | Multi-object tracking |
| `reportlab` | PDF report generation |
| `pandas` + `altair` | Data wrangling + legacy charts |

## Internationalization (i18n)

SafeSight supports **English** and **Hindi** (हिन्दी) out of the box. The language selector is in the sidebar.

### How it works
- All UI strings are stored in `locales/en.json` and `locales/hi.json`
- The `i18n.py` module provides `t("dotted.key")` for lookups with automatic fallback to English
- Supports string interpolation: `t("reports.generating_for", name="Jharia", subsidiary="BCCL")`

### Adding a new language
1. Copy `locales/en.json` to `locales/<code>.json` (e.g. `locales/mr.json` for Marathi)
2. Translate all values (keep the keys in English)
3. Set `"lang_name"` and `"lang_native"` at the top
4. Restart the app — the new language appears automatically in the sidebar

## Key Features

**Core Platform & Architecture:**
- **Environmental Monitoring:** Live IoT sensor feeds (Air quality, dust, gas) integrated into the platform.
- **Multi-tenant Architecture:** Designed for scalable cloud deployment and enterprise management.
- **Robust Database Support:** Zero-setup `sqlite:///` fallback for immediate local development, with explicit `postgresql+psycopg2://` support for production.

**Rich UI & Interactive Analytics:**
- **Modern SVG Assets:** Crisp, responsive SVG logos (`assets/logo.svg` and `assets/icon.svg`) that automatically adapt to light and dark Streamlit themes.
- **Streamlit-AgGrid Integration:** Advanced dataframes in Compliance/Inspections featuring grouping, complex filtering, and instant Excel exports.
- **Plotly & Echarts:** 3D interactive site scatter plots, animated timelines, and live IoT gauge widgets for comprehensive site oversight.
- **Map Cross-Filtering:** Click any specific site on the Folium Map to instantly cross-filter the KPIs and charts on the main Dashboard.
- **Unified Branding:** Clean, domain-agnostic UI as the **SafeSight — Industrial Safety Governance Platform**.
