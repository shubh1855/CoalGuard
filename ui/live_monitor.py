# ui/live_monitor.py — CoalGuard adaptation of SafeSight live monitor
from __future__ import annotations

import tempfile
import time
import sys
import os

import streamlit as st

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
from database import SessionLocal, Site
from modules.violation_logger import log_violation_to_db


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


def open_video_source(sidebar):
    if sidebar.source_type == "Upload video":
        if sidebar.uploaded_file is None:
            st.warning("Upload a video first.")
            st.stop()
        tmp = tempfile.NamedTemporaryFile(delete=False)
        tmp.write(sidebar.uploaded_file.getbuffer())
        import cv2  # lazy import — cv2 only needed when streaming
        return cv2.VideoCapture(tmp.name)
    import cv2  # lazy import
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
    sidebar,
    video_placeholder,
    metrics_row,
    alert_box,
    alerter,
    alerter_ready: bool,
) -> None:
    site_id = st.session_state.get("active_site_id", 1)

    if detector.voice:
        detector.voice_enabled = st.session_state.voice_enabled
        detector.voice.set_repeat_interval(sidebar.zone_repeat_interval)
        if st.session_state.voice_enabled:
            detector.voice.enable()
        else:
            detector.voice.disable()

    apply_zone(detector, sidebar.zone_mode, sidebar.manual_zone_points)

    cap = open_video_source(sidebar)

    if not cap.isOpened():
        st.error("Cannot open video source.")
        st.stop()

    while st.session_state.running:
        ret, frame = cap.read()
        if not ret:
            break

        result = detector.process_frame(frame)
        st.session_state.frames_processed += 1

        # Log new violations to CoalGuard DB
        if hasattr(result, 'new_violations') and result.new_violations:
            for worker_id, violation_type, img_path in result.new_violations:
                try:
                    db = SessionLocal()
                    log_violation_to_db(db, site_id=site_id, worker_id=worker_id,
                                        violation_type=violation_type, image_path=img_path)
                    db.close()
                except Exception:
                    pass  # Non-fatal: CSV logging still works

        maybe_send_email(alerter, alerter_ready, result)

        import cv2  # lazy import
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
    """Standalone render for CoalGuard nav."""
    st.subheader("Live Safety Monitor")
    site_id = render_site_selector()
    st.info(f"Monitoring site ID: {site_id}. Use the main SafeSight app for full CV controls, or integrate via the sidebar.")
    st.markdown("To run the full live monitor, launch `streamlit run app.py` from the project root.")
