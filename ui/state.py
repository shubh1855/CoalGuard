from __future__ import annotations

import streamlit as st


DEFAULT_SESSION_STATE = {
    "running": False,
    "alerts": [],
    "frames_processed": 0,
    "session_epoch": None,
    "voice_enabled": False,
    "alert_email_count": 0,
    "alert_last_sent": None,
    "alert_last_error": None,
    "alerts_enabled": False,
    "zone_source": "NONE",   # kept in sync by update_metrics() each frame
    "zone_mode":   "auto",   # kept in sync by render_sidebar() each render
    "manual_zone_points": [],
    "manual_zone_config_open": False,
    "manual_zone_frame": None,
    "manual_zone_frame_size": None,
    "manual_zone_canvas_rev": 0,
}


def initialize_session_state() -> None:
    for key, default in DEFAULT_SESSION_STATE.items():
        if key not in st.session_state:
            st.session_state[key] = default
