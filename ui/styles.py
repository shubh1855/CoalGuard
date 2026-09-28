APP_STYLES = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@400;500;600;700&display=swap');

:root {
    --bg-main: #08111f;
    --bg-card: rgba(13,22,38,0.92);
    --bg-card-strong: #0f1b31;
    --border: rgba(148,163,184,0.14);
    --border-strong: rgba(125,211,252,0.24);
    --text-main: #e5eefc;
    --text-muted: #93a4bd;
    --text-soft: #6f829d;
    --danger-bg: rgba(127,29,29,0.32);
    --danger-text: #fecaca;
}

html, body, [class*="css"] { font-family: 'Space Grotesk', sans-serif; color: var(--text-main); }

body, .stApp {
    background:
        radial-gradient(900px 520px at 12% 10%, rgba(31,93,155,0.28) 0%, rgba(8,17,31,0) 60%),
        radial-gradient(760px 460px at 88% 2%,  rgba(21,128,61,0.16) 0%, rgba(8,17,31,0) 58%),
        linear-gradient(180deg, #050a14 0%, var(--bg-main) 55%, #050a14 100%);
}

[data-testid="stAppViewContainer"] > .main { background: transparent; }
[data-testid="stSidebar"] {
    background: linear-gradient(180deg, rgba(5,10,20,0.98) 0%, rgba(12,22,40,0.96) 100%);
    border-right: 1px solid var(--border);
}
[data-testid="stSidebar"] * { color: var(--text-main); }

.block-container { max-width: 100%; padding: 1rem 1.5rem 2rem 1.5rem; }
.app-shell { padding: 0.5rem 0 2rem 0; }

.title-bar {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 1rem;
    padding: 1.25rem 1.5rem;
    border-radius: 20px;
    background: linear-gradient(120deg, rgba(11,18,32,0.98) 0%, rgba(17,34,58,0.96) 58%, rgba(10,18,33,0.98) 100%);
    box-shadow: 0 20px 54px rgba(0,0,0,0.32);
    border: 1px solid var(--border-strong);
}
.title-bar h1 { font-size: 1.8rem; margin: 0; }

/* ── Status pills (header) ──────────────────────────────────────────── */
.voice-pill-on, .email-pill-on, .zone-pill-on {
    display: inline-block;
    background: rgba(34,197,94,0.15);
    color: #86efac;
    border: 1px solid rgba(34,197,94,0.3);
    border-radius: 999px;
    padding: 0.28rem 0.75rem;
    font-size: 0.8rem;
    font-weight: 600;
}

.voice-pill-off, .email-pill-off, .zone-pill-off {
    display: inline-block;
    background: rgba(148,163,184,0.1);
    color: var(--text-muted);
    border: 1px solid var(--border);
    border-radius: 999px;
    padding: 0.28rem 0.75rem;
    font-size: 0.8rem;
    font-weight: 600;
}

/* Auto zone pill — orange tint to match cone/sign colour on video */
.zone-pill-auto {
    display: inline-block;
    background: rgba(251,146,60,0.15);
    color: #fdba74;
    border: 1px solid rgba(251,146,60,0.35);
    border-radius: 999px;
    padding: 0.28rem 0.75rem;
    font-size: 0.8rem;
    font-weight: 600;
}

.email-pill-error {
    display: inline-block;
    background: rgba(239,68,68,0.2);
    color: #fca5a5;
    border: 1px solid rgba(239,68,68,0.4);
    border-radius: 999px;
    padding: 0.28rem 0.75rem;
    font-size: 0.8rem;
    font-weight: 600;
}

.voice-speaking {
    display: inline-block;
    background: rgba(251,191,36,0.15);
    color: #fde68a;
    border: 1px solid rgba(251,191,36,0.3);
    border-radius: 999px;
    padding: 0.28rem 0.75rem;
    font-size: 0.8rem;
    font-weight: 600;
    animation: pulse 1s ease-in-out infinite;
}

@keyframes pulse { 0%,100%{opacity:1} 50%{opacity:0.55} }

/* ── Alert pills (right panel) ──────────────────────────────────────── */
.alert-pill {
    display: block;
    width: 100%;
    box-sizing: border-box;
    background: var(--danger-bg);
    color: var(--danger-text);
    padding: 0.55rem 0.8rem;
    border-radius: 12px;
    font-size: 0.85rem;
    font-weight: 600;
    border: 1px solid rgba(248,113,113,0.18);
    margin-bottom: 0.6rem;
}

.zone-alert-pill {
    display: block;
    width: 100%;
    box-sizing: border-box;
    background: rgba(239,68,68,0.2);
    color: #fca5a5;
    padding: 0.6rem 0.9rem;
    border-radius: 12px;
    font-size: 0.88rem;
    font-weight: 700;
    border: 1px solid rgba(239,68,68,0.4);
    margin-bottom: 0.6rem;
    letter-spacing: 0.02em;
}

/* ── Zone source badges (sidebar) ───────────────────────────────────── */
.zone-source-manual {
    display: inline-block;
    background: rgba(148,163,184,0.12);
    color: #cbd5e1;
    border: 1px solid rgba(148,163,184,0.28);
    border-radius: 999px;
    padding: 0.22rem 0.7rem;
    font-size: 0.78rem;
    font-weight: 600;
}

.zone-source-cones {
    display: inline-block;
    background: rgba(251,146,60,0.14);
    color: #fdba74;
    border: 1px solid rgba(251,146,60,0.32);
    border-radius: 999px;
    padding: 0.22rem 0.7rem;
    font-size: 0.78rem;
    font-weight: 600;
}

.zone-source-sign {
    display: inline-block;
    background: rgba(52,211,153,0.12);
    color: #6ee7b7;
    border: 1px solid rgba(52,211,153,0.28);
    border-radius: 999px;
    padding: 0.22rem 0.7rem;
    font-size: 0.78rem;
    font-weight: 600;
}

.zone-source-none {
    display: inline-block;
    background: transparent;
    color: var(--text-soft);
    border: 1px dashed rgba(148,163,184,0.2);
    border-radius: 999px;
    padding: 0.22rem 0.7rem;
    font-size: 0.78rem;
    font-weight: 600;
}

/* ── Misc ───────────────────────────────────────────────────────────── */
.footer-note { color: var(--text-soft); font-size: 0.85rem; }

.sidebar-brand {
    display: flex;
    flex-direction: column;
    align-items: flex-start;
    text-align: left;
    padding: 0.15rem 0 0.75rem 0;
}

.sidebar-brand img {
    width: min(42%, 84px);
    max-width: 84px;
    margin: 0 0 0.5rem 0;
    display: block;
    filter: drop-shadow(0 18px 34px rgba(0,0,0,0.34));
}

.sidebar-brand-title { font-size: 1.35rem; font-weight: 700; color: var(--text-main); }
.sidebar-brand-copy  { color: var(--text-muted); font-size: 0.9rem; }
.view-switch-label {
    font-size: 0.9rem;
    font-weight: 600;
    color: var(--text-main);
    margin-bottom: 0.35rem;
}

.empty-feed {
    min-height: 360px;
    display: flex;
    align-items: center;
    justify-content: center;
    text-align: center;
    border-radius: 16px;
    border: 1px dashed rgba(148,163,184,0.24);
    background: linear-gradient(180deg, rgba(13,22,38,0.92), rgba(10,18,32,0.96));
    color: var(--text-muted);
    padding: 1.5rem;
}

.zone-editor-card {
    padding: 1rem 1.1rem 1.25rem 1.1rem;
    border-radius: 18px;
    background: linear-gradient(180deg, rgba(13,22,38,0.92), rgba(10,18,32,0.96));
    border: 1px solid var(--border);
    margin-bottom: 1.2rem;
}

[data-testid="stImage"] img { border-radius: 16px; }
[data-testid="stImage"] button[title="View fullscreen"] { display: none !important; }
[data-testid="stMetric"] {
    background: var(--bg-card-strong);
    border: 1px solid var(--border);
    border-radius: 14px;
    padding: 0.85rem 1rem;
}
[data-testid="stMetricLabel"],
[data-testid="stMetricValue"] { color: var(--text-main); }

[data-baseweb="radio"] label,
[data-baseweb="checkbox"] label,
.stSelectbox label,
.stTextInput label,
.stTextArea label,
.stSlider label,
.stFileUploader label,
.stNumberInput label { color: var(--text-main); }

[data-testid="stSidebar"] [role="radiogroup"] {
    gap: 0.45rem;
}

[data-testid="stSidebar"] [role="radiogroup"] label {
    background: rgba(9,17,31,0.92);
    border: 1px solid var(--border);
    border-radius: 12px;
    padding: 0.45rem 0.75rem;
}

.stCaption, .stMarkdown p { color: var(--text-muted); }

.stTextInput input,
.stTextArea textarea,
.stNumberInput input {
    background: rgba(9,17,31,0.92);
    color: var(--text-main);
    border: 1px solid var(--border);
}

.stButton button {
    width: 100%;
    background: linear-gradient(180deg, #16314e 0%, #10243b 100%);
    color: var(--text-main);
    border: 1px solid var(--border-strong);
}

.stButton button:hover { border-color: rgba(76,201,240,0.38); color: #ffffff; }

@media (max-width: 1200px) {
  .metric-grid { grid-template-columns: repeat(2,minmax(0,1fr)); }
}
</style>
"""
