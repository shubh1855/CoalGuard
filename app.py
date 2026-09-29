# app.py — SafeSight entry point
import streamlit as st
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from database import init_db
from i18n import t, get_language, set_language, LANGUAGES

init_db()

st.set_page_config(
    page_title="SafeSight",
    page_icon="assets/icon.svg",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Language selector (top of sidebar) ──
lang_codes = list(LANGUAGES.keys())
lang_labels = list(LANGUAGES.values())
current_lang = get_language()
current_idx = lang_codes.index(current_lang) if current_lang in lang_codes else 0

selected_label = st.sidebar.selectbox(
    t('app.language'),
    lang_labels,
    index=current_idx,
    key="lang_selector",
)
selected_code = lang_codes[lang_labels.index(selected_label)]
if selected_code != get_language():
    set_language(selected_code)
    st.rerun()

st.sidebar.divider()
st.logo("assets/logo.svg", icon_image="assets/icon.svg")
st.sidebar.title(t('app.title'))
st.sidebar.caption(t("app.subtitle"))
st.sidebar.divider()

page = st.sidebar.radio(t("app.nav_label"), [
    t("app.pages.dashboard"),
    t("app.pages.live_monitor"),
    t("app.pages.compliance"),
    t("app.pages.inspections"),
    t("app.pages.map"),
    t("app.pages.reports"),
])

st.sidebar.divider()

if page == t("app.pages.dashboard"):
    from ui.dashboard import render
    render()
elif page == t("app.pages.live_monitor"):
    from ui.live_monitor import render
    render()
elif page == t("app.pages.compliance"):
    from ui.compliance import render
    render()
elif page == t("app.pages.inspections"):
    from ui.inspections import render
    render()
elif page == t("app.pages.map"):
    from ui.map_view import render
    render()
elif page == t("app.pages.reports"):
    from ui.reports import render
    render()
