# i18n.py — Internationalization helper for SafeSight
"""
Usage:
    from i18n import t, get_language, set_language, LANGUAGES

    # In the sidebar (done once in app.py):
    set_language(lang_code)

    # Anywhere in UI code:
    t("dashboard.filter_site")          # → "Filter by Mine Site" or Hindi equivalent
    t("reports.generating_for", name="Jharia", subsidiary="BCCL")  # with interpolation
"""
import json
import os
import streamlit as st
from functools import lru_cache

LOCALES_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "locales")
DEFAULT_LANG = "en"


@lru_cache(maxsize=8)
def _load_locale(lang_code: str) -> dict:
    """Load and cache a locale JSON file."""
    path = os.path.join(LOCALES_DIR, f"{lang_code}.json")
    if not os.path.exists(path):
        path = os.path.join(LOCALES_DIR, f"{DEFAULT_LANG}.json")
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def available_languages() -> dict[str, str]:
    """Return dict of {code: native_name} for all available locales."""
    langs = {}
    for fname in sorted(os.listdir(LOCALES_DIR)):
        if fname.endswith(".json"):
            code = fname.replace(".json", "")
            data = _load_locale(code)
            langs[code] = data.get("lang_native", code)
    return langs


# Convenience alias
LANGUAGES = available_languages()


def get_language() -> str:
    """Get the current language code from session state."""
    return st.session_state.get("lang", DEFAULT_LANG)


def set_language(lang_code: str):
    """Set the current language in session state."""
    st.session_state["lang"] = lang_code


def t(key: str, **kwargs) -> str:
    """
    Translate a dotted key like 'dashboard.filter_site'.

    Supports Python str.format() interpolation:
        t("reports.generating_for", name="Jharia", subsidiary="BCCL")
    """
    lang = get_language()
    data = _load_locale(lang)
    fallback = _load_locale(DEFAULT_LANG)

    parts = key.split(".")
    # Walk the nested dict
    value = data
    fb_value = fallback
    for part in parts:
        if isinstance(value, dict):
            value = value.get(part)
        else:
            value = None
        if isinstance(fb_value, dict):
            fb_value = fb_value.get(part)
        else:
            fb_value = None

    result = value if value is not None else fb_value
    if result is None:
        return key  # Return the key itself as last resort

    if kwargs:
        try:
            result = result.format(**kwargs)
        except (KeyError, IndexError):
            pass

    return result
