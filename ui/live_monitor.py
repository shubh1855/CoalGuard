# ui/live_monitor.py — CoalGuard adaptation of SafeSight live monitor
from __future__ import annotations

import tempfile
import time
import sys
import os
from pathlib import Path

import streamlit as st

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
from database import SessionLocal, Site
from modules.violation_logger import log_violation_to_db
from modules.alerts import ZoneIntrusionAlerter
from modules.tracked_detector import TrackedSafeSightDetector
from ui.components import render_feed_caption, render_header, render_sidebar
from ui.state import initialize_session_state
from ui.styles import APP_STYLES
from ui.zone_editor import render_zone_editor

SIGN_MODEL_PATH = "models/sign_best.pt"


@st.cache_resource
def load_detector(
    model_path: str,
    conf: float,
    source_type: str,
    session_epoch: int,
) -> TrackedSafeSightDetector:
    sign_path = SIGN_MODEL_PATH if Path(SIGN_MODEL_PATH).exists() else None
    if sign_path is None:
        st.warning(
            f"Sign model not found at '{SIGN_MODEL_PATH}' — "
            "Auto zone via sign detection is disabled. "
        )
    return TrackedSafeSightDetector(
        model_path=model_path,
        conf_threshold=conf,
        source_type=source_type,
        session_epoch=session_epoch,
        enable_voice=True,
        sign_model_path=sign_path,
        zone_mode="auto",
    )


def _get_sites():
    db = SessionLocal()
    sites = db.query(Site).all()
    db.close()
    return sites


def render_site_selector():
    """Render site selector in sidebar. Returns selected site_id."""
    sites = _get_sites()
    if not sites:
        st.sidebar.warning("No sites in DB. Run seed.py.")
        return 1
    site_names = [s.name for s in sites]
    selected = st.sidebar.selectbox("Active Mine Site", site_names, key="coalguard_site")
    site_id = next(s.id for s in sites if s.name == selected)
    st.session_state["active_site_id"] = site_id
    return site_id


def apply_zone(detector, zone_mode: str, manual_zone_points: list) -> None:
    if zone_mode == "off":
        detector.clear_zone()
        detector.set_zone_mode("manual")
    elif zone_mode == "manual":
        if manual_zone_points:
            detector.set_zone(manual_zone_points, source="MANUAL")
            detector.set_zone_mode("manual")
        else:
            detector.clear_zone()
            detector.set_zone_mode("manual")
            st.warning("Manual zone enabled but no polygon configured.")
    else:
        detector.set_zone_mode("auto")


def open_video_source(sidebar_config):
    if sidebar_config.source_type == "Upload video":
        if sidebar_config.uploaded_file is None:
            st.warning("Upload a video first.")
            st.stop()
        tmp = tempfile.NamedTemporaryFile(delete=False)
        tmp.write(sidebar_config.uploaded_file.getbuffer())
        import cv2
        return cv2.VideoCapture(tmp.name)
    import cv2
    return cv2.VideoCapture(0)


def update_metrics(metrics_row, result) -> None:
    st.session_state.zone_source = result.zone_source
    metrics_row.empty()
    with metrics_row.container():
        cols = st.columns(3)
        cols[0].metric("Workers", result.total_workers)
        cols[1].metric("Violations", result.violation_count)
        cols[2].metric("FPS", f"{result.fps:.1f}")


def maybe_send_email(alerter, alerter_ready: bool, result) -> None:
    if not (alerter_ready and st.session_state.alerts_enabled):
        return
    try:
        sent = alerter.notify_if_needed(result)
        if sent:
            st.session_state.alert_email_count += 1
            st.session_state.alert_last_sent = time.strftime("%H:%M:%S")
            st.session_state.alert_last_error = None
    except Exception as exc:
        st.session_state.alert_last_error = str(exc)


def render_idle_state(video_placeholder, alert_box) -> None:
    video_placeholder.markdown(
        "<div style='padding:60px;text-align:center;color:#888;'>Start monitoring to display the live safety stream.</div>",
        unsafe_allow_html=True,
    )
    alert_box.empty()


def run_monitoring_loop(
    detector,
    sidebar_config,
    video_placeholder,
    metrics_row,
    alert_box,
    alerter,
    alerter_ready: bool,
) -> None:
    site_id = st.session_state.get("active_site_id", 1)

    if detector.voice:
        detector.voice_enabled = st.session_state.voice_enabled
        detector.voice.set_repeat_interval(sidebar_config.zone_repeat_interval)
        if st.session_state.voice_enabled:
            detector.voice.enable()
        else:
            detector.voice.disable()

    apply_zone(detector, sidebar_config.zone_mode, sidebar_config.manual_zone_points)

    cap = open_video_source(sidebar_config)

    if not cap.isOpened():
        st.error("Cannot open video source.")
        st.stop()

    while st.session_state.running:
        ret, frame = cap.read()
        if not ret:
            break

        result = detector.process_frame(frame)
        st.session_state.frames_processed += 1

        if hasattr(result, 'new_violations') and result.new_violations:
            for worker_id, violation_type, img_path in result.new_violations:
                try:
                    db = SessionLocal()
                    log_violation_to_db(db, site_id=site_id, worker_id=worker_id,
                                        violation_type=violation_type, image_path=img_path)
                    db.close()
                except Exception:
                    pass

        maybe_send_email(alerter, alerter_ready, result)

        import cv2
        rgb = cv2.cvtColor(result.frame, cv2.COLOR_BGR2RGB)
        video_placeholder.image(rgb, channels="RGB", use_container_width=True)

        update_metrics(metrics_row, result)

        st.session_state.alerts = (
            list(reversed(result.alerts)) + st.session_state.alerts
        )[:10]
        with alert_box.container():
            for alert in st.session_state.alerts:
                st.warning(alert)

        time.sleep(0.01)

    cap.release()
    st.session_state.running = False
    st.success("Monitoring stopped.")


def render():
    st.markdown(APP_STYLES, unsafe_allow_html=True)
    initialize_session_state()

    try:
        alerter = ZoneIntrusionAlerter.from_env()
        ALERTER_READY = True
        ALERTER_MISSING = ""
    except EnvironmentError as env_err:
        alerter = None
        ALERTER_READY = False
        ALERTER_MISSING = str(env_err)

    render_site_selector()
    
    sidebar_config = render_sidebar(load_detector, alerter, ALERTER_READY, ALERTER_MISSING)

    with st.container():
        st.markdown("<div class='app-shell'>", unsafe_allow_html=True)
        render_header(sidebar_config.use_manual_zone, ALERTER_READY)
        st.write("")

        if sidebar_config.zone_mode == "manual":
            render_zone_editor()

        left, right = st.columns([2.2, 1], gap="large")

        with left:
            metrics_row = st.empty()
            st.write("")
            feed_title, feed_caption = render_feed_caption(
                sidebar_config.source_type,
                sidebar_config.confidence,
            )
            st.subheader(feed_title)
            st.caption(feed_caption)
            video_placeholder = st.empty()

        with right:
            st.subheader("Active Alerts")
            alert_box = st.empty()

        if st.session_state.running:
            if not Path(sidebar_config.model_path).exists():
                st.error("Model file not found.")
                st.stop()

            detector = load_detector(
                sidebar_config.model_path,
                sidebar_config.confidence,
                sidebar_config.source_type,
                st.session_state.session_epoch,
            )
            
            zone_err = getattr(getattr(detector, 'detector', detector), 'zone_detector_error', None)
            if zone_err:
                st.error(f"⚠️ Sign model failed to load — Auto zone (sign) is disabled.\n"
                    f"```\n{zone_err}\n```\n"
                    f"Check that `models/sign_best.pt` exists and is a valid YOLOv8 model."
                )

            run_monitoring_loop(
                detector=detector,
                sidebar_config=sidebar_config,
                video_placeholder=video_placeholder,
                metrics_row=metrics_row,
                alert_box=alert_box,
                alerter=alerter,
                alerter_ready=ALERTER_READY,
            )
        else:
            render_idle_state(video_placeholder, alert_box)

        st.write("")
        st.markdown("</div>", unsafe_allow_html=True)
