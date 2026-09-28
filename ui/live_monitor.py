import tempfile
import time
import sys
import os
from pathlib import Path

import streamlit as st

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
from database import SessionLocal, Site
from modules.violation_logger import log_violation_to_db
from modules.tracked_detector import TrackedSafeSightDetector
from ui.zone_editor import render_zone_editor, capture_reference_frame
from i18n import t

SIGN_MODEL_PATH = "models/sign_best.pt"

@st.cache_resource
def load_detector(model_path: str, conf: float, source_type: str, session_epoch: int):
    sign_path = SIGN_MODEL_PATH if Path(SIGN_MODEL_PATH).exists() else None
    if sign_path is None:
        st.sidebar.warning(t("monitor.sign_model_warn", path=SIGN_MODEL_PATH))
        
    return TrackedSafeSightDetector(
        model_path=model_path,
        conf_threshold=conf,
        source_type=source_type,
        session_epoch=session_epoch,
        enable_voice=True,
        sign_model_path=sign_path,
        zone_mode="auto",
    )

def init_state():
    if "running" not in st.session_state:
        st.session_state.running = False
    if "alerts" not in st.session_state:
        st.session_state.alerts = []
    if "frames_processed" not in st.session_state:
        st.session_state.frames_processed = 0
    if "session_epoch" not in st.session_state:
        st.session_state.session_epoch = int(time.time())
    if "voice_enabled" not in st.session_state:
        st.session_state.voice_enabled = False
    if "manual_zone_points" not in st.session_state:
        st.session_state.manual_zone_points = []
    if "manual_zone_config_open" not in st.session_state:
        st.session_state.manual_zone_config_open = False
    if "manual_zone_canvas_rev" not in st.session_state:
        st.session_state.manual_zone_canvas_rev = 0

def render():
    init_state()
    st.title(t("monitor.title"))
    st.write(t("monitor.subtitle"))

    # --- Sidebar Controls ---
    st.sidebar.header(t("monitor.controls"))

    db = SessionLocal()
    sites = db.query(Site).all()
    db.close()
    if not sites:
        st.sidebar.warning(t("monitor.no_sites"))
        return
    
    site_names = [s.name for s in sites]
    selected_site = st.sidebar.selectbox(t("monitor.active_site"), site_names, key="SafeSight_site")
    site_id = next(s.id for s in sites if s.name == selected_site)
    st.session_state["active_site_id"] = site_id
    
    st.sidebar.divider()
    confidence = st.sidebar.slider(t("monitor.confidence"), 0.1, 0.9, 0.45, 0.05)
    source_type = st.sidebar.radio(t("monitor.video_source"), [t("monitor.upload_video"), t("monitor.webcam")])
    
    uploaded_file = None
    if source_type == t("monitor.upload_video"):
        uploaded_file = st.sidebar.file_uploader(t("monitor.upload_label"), type=["mp4", "avi", "mov"])
        
    st.sidebar.divider()
    zone_labels = [t("monitor.auto_detect"), t("monitor.manual"), t("monitor.off")]
    zone_mode_label = st.sidebar.radio(t("monitor.restricted_zone"), zone_labels)
    zone_mode = "auto" if zone_mode_label == zone_labels[0] else ("manual" if zone_mode_label == zone_labels[1] else "off")
    
    if zone_mode == "manual":
        col1, col2 = st.sidebar.columns(2)
        if col1.button(t("monitor.configure_zone"), use_container_width=True, key="btn_config_zone"):
            frame, err = capture_reference_frame(source_type, uploaded_file)
            if err:
                st.sidebar.error(err)
            else:
                st.session_state.manual_zone_frame = frame
                st.session_state.manual_zone_config_open = True
                st.session_state.manual_zone_canvas_rev += 1
                if st.session_state.running:
                    st.session_state.running = False
                st.rerun()
        if col2.button(t("monitor.clear_zone"), use_container_width=True, key="btn_clear_zone"):
            st.session_state.manual_zone_points = []
            st.session_state.manual_zone_config_open = False
            
    st.session_state.voice_enabled = st.sidebar.toggle(t("monitor.voice_alerts"), value=st.session_state.voice_enabled)
    
    st.sidebar.divider()
    scol1, scol2 = st.sidebar.columns(2)
    if scol1.button(t("monitor.start"), type="primary", use_container_width=True, key="btn_start_monitor"):
        st.session_state.running = True
        st.session_state.alerts = []
        st.session_state.frames_processed = 0
        st.session_state.session_epoch = int(time.time())
        load_detector.clear()
        st.session_state.manual_zone_config_open = False
        st.rerun()
    if scol2.button(t("monitor.stop"), use_container_width=True, key="btn_stop_monitor"):
        st.session_state.running = False
        st.rerun()

    # --- Manual Zone Editor ---
    if st.session_state.manual_zone_config_open:
        render_zone_editor()
        st.divider()

    # --- Main Metrics ---
    metrics_cols = st.columns(3)
    metrics_row = [metrics_cols[0].empty(), metrics_cols[1].empty(), metrics_cols[2].empty()]
    
    # Defaults
    metrics_row[0].metric(t("monitor.workers_detected"), 0)
    metrics_row[1].metric(t("monitor.violations"), 0)
    metrics_row[2].metric(t("monitor.fps"), "0.0")

    st.divider()

    # --- Playback & Alerts ---
    main_cols = st.columns([2.5, 1], gap="large")
    video_placeholder = main_cols[0].empty()
    alert_box = main_cols[1].empty()

    if not st.session_state.running:
        video_placeholder.info(t("monitor.click_start"))
        with alert_box.container():
            st.subheader(t("monitor.active_alerts"))
            st.write(t("monitor.no_alerts"))
        return

    # --- Run Loop ---
    model_path = "models/best.pt"
    if not Path(model_path).exists():
        st.error(t("monitor.model_not_found", path=model_path))
        st.stop()

    detector = load_detector(model_path, confidence, source_type, st.session_state.session_epoch)

    # Zone configuration
    if zone_mode == "off":
        detector.clear_zone()
        detector.set_zone_mode("manual")
    elif zone_mode == "manual":
        pts = st.session_state.get("manual_zone_points", [])
        if pts:
            detector.set_zone(pts, source="MANUAL")
            detector.set_zone_mode("manual")
        else:
            detector.clear_zone()
            detector.set_zone_mode("manual")
            st.warning(t("monitor.manual_zone_warn"))
    else:
        detector.set_zone_mode("auto")

    # Voice configuration
    if detector.voice:
        if st.session_state.voice_enabled:
            detector.voice.enable()
        else:
            detector.voice.disable()

    # Video Capture
    if source_type == t("monitor.upload_video"):
        if not uploaded_file:
            st.error(t("monitor.upload_error"))
            st.stop()
        tmp = tempfile.NamedTemporaryFile(delete=False)
        tmp.write(uploaded_file.getbuffer())
        import cv2
        cap = cv2.VideoCapture(tmp.name)
    else:
        import cv2
        cap = cv2.VideoCapture(0)

    if not cap.isOpened():
        st.error(t("monitor.source_error"))
        st.stop()

    video_placeholder.info(t("monitor.starting"))

    while st.session_state.running:
        ret, frame = cap.read()
        if not ret:
            st.info(t("monitor.stream_ended"))
            break

        result = detector.process_frame(frame)
        st.session_state.frames_processed += 1

        # Database Logging
        if hasattr(result, 'new_violations') and result.new_violations:
            for worker_id, violation_type, img_path in result.new_violations:
                try:
                    db = SessionLocal()
                    log_violation_to_db(db, site_id=site_id, worker_id=worker_id,
                                        violation_type=violation_type, image_path=img_path)
                    db.close()
                except Exception:
                    pass

        # UI Updates
        import cv2
        rgb = cv2.cvtColor(result.frame, cv2.COLOR_BGR2RGB)
        video_placeholder.image(rgb, channels="RGB", use_column_width=True)

        metrics_row[0].metric(t("monitor.workers_detected"), result.total_workers)
        metrics_row[1].metric(t("monitor.violations"), result.violation_count)
        metrics_row[2].metric(t("monitor.fps"), f"{result.fps:.1f}")

        # Update Alerts Box
        new_alerts = getattr(result, "alerts", [])
        st.session_state.alerts = (list(reversed(new_alerts)) + st.session_state.alerts)[:10]
        
        with alert_box.container():
            st.subheader(t("monitor.active_alerts"))
            if not st.session_state.alerts:
                st.write(t("monitor.no_active_alerts"))
            for alert in st.session_state.alerts:
                if "ZONE" in alert.upper():
                    st.error(alert)
                else:
                    st.warning(alert)

        time.sleep(0.01)

    cap.release()
    st.session_state.running = False
    st.success(t("monitor.stopped"))
