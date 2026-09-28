from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import time
from typing import Callable

import streamlit as st

from ui.assets import load_logo
from ui.zone_editor import capture_reference_frame


@dataclass
class SidebarConfig:
    view_mode: str
    model_path: str
    confidence: float
    source_type: str
    uploaded_file: object | None
    zone_mode: str          # "manual" | "auto"  ← replaces use_manual_zone bool
    zone_input: str
    manual_zone_points: list[tuple[int, int]]
    zone_repeat_interval: int
    selected_csv_path: str | None

    # Keep backward-compat property so any code still reading .use_manual_zone works
    @property
    def use_manual_zone(self) -> bool:
        return self.zone_mode == "manual"


def draw_status_alerts(alert_box, alerts: list[str]) -> None:
    alert_box.empty()
    with alert_box.container():
        if not alerts:
            st.write("No alerts")
            return
        for alert in alerts[:10]:
            pill_class = "zone-alert-pill" if "ZONE" in alert.upper() else "alert-pill"
            st.markdown(
                f"<span class='{pill_class}'>{alert}</span>",
                unsafe_allow_html=True,
            )


def render_sidebar(
    load_detector_fn: Callable,
    alerter,
    alerter_ready: bool,
    alerter_missing: str,
) -> SidebarConfig:
    with st.sidebar:
        st.divider()
        st.markdown("**Live Monitor Controls**")

        model_path = "models/best.pt"
        confidence = st.slider("Detection confidence", 0.1, 0.9, 0.45, 0.05)
        
        view_mode = "Dashboard" # hardcode view mode, we don't need 'Graphs' view here


        col1, col2 = st.columns(2)
        if col1.button("Start"):
            st.session_state.running = True
            st.session_state.alerts = []
            st.session_state.frames_processed = 0
            st.session_state.session_epoch = int(time.time())
            load_detector_fn.clear()
        if col2.button("Stop"):
            st.session_state.running = False

        st.divider()
        source_type = st.radio("Video Source", ["Upload video", "Webcam"], index=0)
        uploaded_file = None

        if source_type == "Upload video":
            uploaded_file = st.file_uploader("Upload Video", type=["mp4", "avi", "mov"])

        data_dir = Path(__file__).resolve().parent.parent / "data"
        csv_files = sorted(data_dir.glob("violations_*.csv"), reverse=True)
        csv_labels = [path.name for path in csv_files]
        selected_csv_path = None
        if view_mode == "Graphs":
            st.divider()
            st.markdown("#### Graph Data")
            if csv_files:
                selected_csv_name = st.selectbox(
                    "CSV Session",
                    csv_labels,
                    index=0,
                )
                selected_csv_path = str(data_dir / selected_csv_name)
            else:
                st.caption("No CSV sessions available yet.")

        # ── Zone Mode ─────────────────────────────────────────────────────────
        st.divider()
        st.markdown("#### Restricted Zone")

        zone_mode_label = st.radio(
            "Zone Mode",
            ["Auto-Detect", "Manual", "Off"],
            index=0,
            horizontal=True,
            help=(
                "Auto-Detect: zone is inferred from safety cones or danger signs in the frame.\n"
                "Manual: draw a polygon by entering coordinates below.\n"
                "Off: disable zone detection entirely."
            ),
        )
        zone_mode = "auto" if zone_mode_label == "Auto-Detect" else ("manual" if zone_mode_label == "Manual" else "off")

        zone_input = ""
        # Mirror zone_mode into session state for header pill sync
        st.session_state["zone_mode"] = zone_mode
        if zone_mode == "manual":
            saved_points = st.session_state.get("manual_zone_points", [])
            status = (
                f"Manual zone configured with {len(saved_points)} points."
                if saved_points
                else "No manual zone configured yet."
            )
            st.caption(status)
            cfg_col, clear_col = st.columns(2)
            if cfg_col.button("Configure Zone", use_container_width=True):
                frame, error = capture_reference_frame(source_type, uploaded_file)
                if error:
                    st.warning(error)
                else:
                    st.session_state.manual_zone_frame = frame
                    st.session_state.manual_zone_frame_size = frame.shape[:2]
                    st.session_state.manual_zone_config_open = True
                    st.session_state.manual_zone_canvas_rev += 1
                    if st.session_state.running:
                        st.session_state.running = False
                    st.rerun()
            if clear_col.button("Clear Zone", use_container_width=True):
                st.session_state.manual_zone_points = []
                st.session_state.manual_zone_config_open = False
                st.session_state.manual_zone_frame = None
                st.session_state.manual_zone_frame_size = None
                st.session_state.zone_source = "NONE"
            if saved_points:
                st.caption(
                    "Saved points: "
                    + ", ".join(f"({x},{y})" for x, y in saved_points[:4])
                    + (" ..." if len(saved_points) > 4 else "")
                )
            else:
                st.caption("Open calibration to draw a polygon over the restricted area.")
        elif zone_mode == "off":
            st.caption("Zone detection is **disabled**. No restricted zone will be drawn or enforced.")
        else:
            # Show live zone source from session state (updated by the monitor loop)
            source = st.session_state.get("zone_source", "NONE")
            _render_zone_source_badge(source)
            st.caption(
                "Zone auto-updates each frame.  "
                "Place ≥ 3 safety cones **or** a visible danger sign in view."
            )
        # ─────────────────────────────────────────────────────────────────────

        st.divider()
        st.markdown("#### Zone Voice Alert")
        st.caption("Voice speaks only when a worker enters the restricted zone.")

        voice_toggle = st.toggle(
            "Enable zone voice alert",
            value=st.session_state.voice_enabled,
            key="voice_toggle_widget",
        )

        if voice_toggle != st.session_state.voice_enabled:
            st.session_state.voice_enabled = voice_toggle
            try:
                if st.session_state.session_epoch is not None:
                    active_detector = load_detector_fn(
                        model_path,
                        confidence,
                        source_type,
                        st.session_state.session_epoch,
                    )
                else:
                    active_detector = None
                if active_detector and active_detector.voice:
                    if voice_toggle:
                        active_detector.voice.enable()
                    else:
                        active_detector.voice.disable()
            except Exception:
                pass

        zone_repeat_interval = 10
        if voice_toggle:
            zone_repeat_interval = st.slider(
                "Repeat alert every X seconds",
                min_value=3,
                max_value=60,
                value=10,
                step=1,
                help="How often the zone alert repeats while someone is still in the zone",
            )
            st.caption(
                f"Alert repeats every **{zone_repeat_interval}s** while the zone remains occupied."
            )

        st.divider()
        st.markdown("#### Email Alert Status")
        st.session_state.alerts_enabled = st.checkbox(
            "Enable email alerts",
            value=st.session_state.alerts_enabled,
            help="Uncheck to pause zone intrusion emails without resetting count or cooldown.",
        )

        if not alerter_ready:
            st.warning(f"Alerts disabled: {alerter_missing}")
        else:
            total = st.session_state.alert_email_count
            last = st.session_state.alert_last_sent
            err = st.session_state.alert_last_error
            cooldown_left = alerter.cooldown_remaining if st.session_state.running else 0.0

            if not st.session_state.alerts_enabled:
                st.caption("Alerts are paused.")
            elif err:
                st.error(f"**Send failed:** {err}")
            elif total == 0:
                st.info("No alerts sent yet.")
            else:
                st.success(f"Last sent at **{last}**")

            col_a, col_b = st.columns(2)
            col_a.metric("Emails sent", total)
            col_b.metric("Cooldown", f"{cooldown_left:.0f}s" if cooldown_left > 0 else "Ready ✓")

            btn1, btn2 = st.columns(2)
            with btn1:
                if st.button("Reset cooldown"):
                    alerter.reset_cooldown()
                    st.toast("Cooldown cleared — next intrusion sends immediately.")
            with btn2:
                if st.button("Send test"):
                    try:
                        alerter.reset_cooldown()

                        class _FakeResult:
                            zone_intrusion_count = 1

                        sent = alerter.notify_if_needed(_FakeResult())
                        if sent:
                            st.session_state.alert_email_count += 1
                            st.session_state.alert_last_sent = time.strftime("%H:%M:%S")
                            st.session_state.alert_last_error = None
                            st.toast("Test email sent.")
                        else:
                            st.toast("Returned False. Check .env credentials.")
                    except Exception as exc:
                        st.session_state.alert_last_error = str(exc)
                        st.toast(str(exc))

        st.divider()
        st.caption("Last model refresh: 5 minutes ago")

    return SidebarConfig(
        view_mode=view_mode,
        model_path=model_path,
        confidence=confidence,
        source_type=source_type,
        uploaded_file=uploaded_file,
        zone_mode=zone_mode,
        zone_input=zone_input,
        manual_zone_points=st.session_state.get("manual_zone_points", []),
        zone_repeat_interval=zone_repeat_interval,
        selected_csv_path=selected_csv_path,
    )


# ── Internal helper ───────────────────────────────────────────────────────────

_ZONE_SOURCE_CLASSES = {
    "MANUAL":     "zone-source-manual",
    "AUTO:CONES": "zone-source-cones",
    "AUTO:SIGN":  "zone-source-sign",
    "NONE":       "zone-source-none",
}
_ZONE_SOURCE_LABELS = {
    "MANUAL":     "● Manual polygon",
    "AUTO:CONES": "◉ Auto — cones",
    "AUTO:SIGN":  "◉ Auto — sign",
    "NONE":       "○ No zone active",
}

def _render_zone_source_badge(source: str) -> None:
    css_class = _ZONE_SOURCE_CLASSES.get(source, "zone-source-none")
    label     = _ZONE_SOURCE_LABELS.get(source, source)
    st.markdown(
        f"<span class='{css_class}'>{label}</span>",
        unsafe_allow_html=True,
    )


# ── Header ────────────────────────────────────────────────────────────────────

def render_header(use_manual_zone: bool, alerter_ready: bool) -> None:
    zone_source = st.session_state.get("zone_source", "NONE")
    zone_mode   = st.session_state.get("zone_mode",   "auto")

    if zone_mode == "off":
        zone_detection_pill_html = "<span class='zone-pill-off'>Zone Detection Off</span>"
    elif zone_mode == "manual":
        zone_detection_pill_html = "<span class='zone-pill-on'>Zone — Manual</span>"
    else:
        if zone_source == "AUTO:CONES":
            zone_detection_pill_html = "<span class='zone-pill-auto'>Zone — Auto: Cones</span>"
        elif zone_source == "AUTO:SIGN":
            zone_detection_pill_html = "<span class='zone-pill-auto'>Zone — Auto: Sign</span>"
        else:
            zone_detection_pill_html = "<span class='zone-pill-auto'>Zone — Auto (scanning…)</span>"

    voice_pill_html = (
        "<span class='voice-pill-on'>Zone Alert On</span>"
        if st.session_state.voice_enabled
        else "<span class='voice-pill-off'>Zone Alert Off</span>"
    )
    if not alerter_ready or st.session_state.alert_last_error:
        email_pill_html = "<span class='email-pill-error'>Email Alerts Error</span>"
    elif st.session_state.alerts_enabled:
        email_pill_html = "<span class='email-pill-on'>Email Alerts On</span>"
    else:
        email_pill_html = "<span class='email-pill-off'>Email Alerts Off</span>"

    st.markdown(
        f"""
        <div class="title-bar">
            <div>
                <h1>SafeSight Safety Command Center</h1>
                <div>Real-time PPE compliance and restricted-zone monitoring</div>
            </div>
            <div style="display:flex;gap:0.6rem;align-items:center;flex-wrap:wrap;">
                {zone_detection_pill_html}
                {voice_pill_html}
                {email_pill_html}
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_feed_caption(source_type: str, confidence: float) -> tuple[str, str]:
    if source_type == "Webcam":
        return (
            "Live Safety Feed",
            f"Source: {source_type} · Confidence ≥ {confidence:.2f} · Live monitoring",
        )
    return (
        "Video Playback",
        f"Source: {source_type} · Confidence ≥ {confidence:.2f} · Recorded footage",
    )
