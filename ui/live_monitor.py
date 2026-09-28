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

SIGN_MODEL_PATH = "models/sign_best.pt"

@st.cache_resource
def load_detector(model_path: str, conf: float, source_type: str, session_epoch: int):
    sign_path = SIGN_MODEL_PATH if Path(SIGN_MODEL_PATH).exists() else None
    if sign_path is None:
        st.sidebar.warning(f"Sign model '{SIGN_MODEL_PATH}' not found. Auto zone is disabled.")
        
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
        st.session_state.alerts = []
        st.session_state.frames_processed = 0
        st.session_state.session_epoch = int(time.time())
        st.session_state.voice_enabled = False
        st.session_state.manual_zone_points = []
        st.session_state.manual_zone_config_open = False

def render():
    init_state()
    st.title("Live Safety Monitor")
    st.write("Real-time PPE compliance and restricted-zone monitoring powered by YOLOv8 and DeepSORT.")

    # --- Sidebar Controls ---
    st.sidebar.header("Monitor Controls")

    db = SessionLocal()
    sites = db.query(Site).all()
    db.close()
    if not sites:
        st.sidebar.warning("No sites in DB. Please run seed.py.")
        return
    
    site_names = [s.name for s in sites]
    selected_site = st.sidebar.selectbox("Active Mine Site", site_names, key="coalguard_site")
    site_id = next(s.id for s in sites if s.name == selected_site)
    st.session_state["active_site_id"] = site_id
    
    st.sidebar.divider()
    confidence = st.sidebar.slider("Detection Confidence", 0.1, 0.9, 0.45, 0.05)
    source_type = st.sidebar.radio("Video Source", ["Upload video", "Webcam"])
    
    uploaded_file = None
    if source_type == "Upload video":
        uploaded_file = st.sidebar.file_uploader("Upload Video", type=["mp4", "avi", "mov"])
        
    st.sidebar.divider()
    zone_mode_label = st.sidebar.radio("Restricted Zone", ["Auto-Detect", "Manual", "Off"])
    zone_mode = "auto" if zone_mode_label == "Auto-Detect" else ("manual" if zone_mode_label == "Manual" else "off")
    
    if zone_mode == "manual":
        col1, col2 = st.sidebar.columns(2)
        if col1.button("Configure Zone", use_container_width=True):
            frame, err = capture_reference_frame(source_type, uploaded_file)
            if err:
                st.sidebar.error(err)
            else:
                st.session_state.manual_zone_frame = frame
                st.session_state.manual_zone_config_open = True
                if st.session_state.running:
                    st.session_state.running = False
                st.rerun()
        if col2.button("Clear Zone", use_container_width=True):
            st.session_state.manual_zone_points = []
            st.session_state.manual_zone_config_open = False
            
    st.session_state.voice_enabled = st.sidebar.toggle("Voice Alerts", value=st.session_state.voice_enabled)
    
    st.sidebar.divider()
    scol1, scol2 = st.sidebar.columns(2)
    if scol1.button("Start", type="primary", use_container_width=True):
        st.session_state.running = True
        st.session_state.alerts = []
        st.session_state.frames_processed = 0
        st.session_state.session_epoch = int(time.time())
        load_detector.clear()
        st.session_state.manual_zone_config_open = False
        st.rerun()
    if scol2.button("Stop", use_container_width=True):
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
    metrics_row[0].metric("Workers Detected", 0)
    metrics_row[1].metric("Violations", 0)
    metrics_row[2].metric("FPS", "0.0")

    st.divider()

    # --- Playback & Alerts ---
    main_cols = st.columns([2.5, 1], gap="large")
    video_placeholder = main_cols[0].empty()
    alert_box = main_cols[1].empty()

    if not st.session_state.running:
        video_placeholder.info("Click **Start** in the sidebar to begin live monitoring.")
        with alert_box.container():
            st.subheader("Active Alerts")
            st.write("No alerts. System idle.")
        return

    # --- Run Loop ---
    model_path = "models/best.pt"
    if not Path(model_path).exists():
        st.error(f"Model file not found at '{model_path}'.")
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
            st.warning("Manual zone is enabled but no points have been drawn yet.")
    else:
        detector.set_zone_mode("auto")

    # Voice configuration
    if detector.voice:
        if st.session_state.voice_enabled:
            detector.voice.enable()
        else:
            detector.voice.disable()

    # Video Capture
    if source_type == "Upload video":
        if not uploaded_file:
            st.error("Please upload a video file in the sidebar before starting.")
            st.stop()
        tmp = tempfile.NamedTemporaryFile(delete=False)
        tmp.write(uploaded_file.getbuffer())
        import cv2
        cap = cv2.VideoCapture(tmp.name)
    else:
        import cv2
        cap = cv2.VideoCapture(0)

    if not cap.isOpened():
        st.error("Cannot open the selected video source.")
        st.stop()

    video_placeholder.info("Starting video stream...")

    while st.session_state.running:
        ret, frame = cap.read()
        if not ret:
            st.info("Video stream ended.")
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

        metrics_row[0].metric("Workers Detected", result.total_workers)
        metrics_row[1].metric("Violations", result.violation_count)
        metrics_row[2].metric("FPS", f"{result.fps:.1f}")

        # Update Alerts Box
        new_alerts = getattr(result, "alerts", [])
        st.session_state.alerts = (list(reversed(new_alerts)) + st.session_state.alerts)[:10]
        
        with alert_box.container():
            st.subheader("Active Alerts")
            if not st.session_state.alerts:
                st.write("No active alerts.")
            for alert in st.session_state.alerts:
                if "ZONE" in alert.upper():
                    st.error(alert)
                else:
                    st.warning(alert)

        time.sleep(0.01)

    cap.release()
    st.session_state.running = False
    st.success("Monitoring stopped.")
