from __future__ import annotations

import tempfile
from typing import Iterable

import cv2
import numpy as np
import streamlit as st
from PIL import Image
from streamlit_drawable_canvas import st_canvas


MAX_CANVAS_WIDTH = 900


def capture_reference_frame(source_type: str, uploaded_file) -> tuple[object | None, str | None]:
    if source_type == "Upload video":
        if uploaded_file is None:
            return None, "Upload a video before configuring a manual zone."
        tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".mp4")
        tmp.write(uploaded_file.getbuffer())
        tmp.flush()
        cap = cv2.VideoCapture(tmp.name)
    else:
        cap = cv2.VideoCapture(0)

    try:
        if not cap.isOpened():
            return None, "Unable to open the selected video source."
        ok, frame = cap.read()
        if not ok or frame is None:
            return None, "Unable to capture a frame for manual zone setup."
        return frame, None
    finally:
        cap.release()


def render_zone_editor() -> None:
    frame = st.session_state.get("manual_zone_frame")
    if frame is None or not st.session_state.get("manual_zone_config_open", False):
        return

    frame_h, frame_w = frame.shape[:2]
    scale = min(1.0, MAX_CANVAS_WIDTH / frame_w)
    canvas_w = max(1, int(frame_w * scale))
    canvas_h = max(1, int(frame_h * scale))
    rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    background = Image.fromarray(rgb_frame)

    st.markdown("<div class='zone-editor-card'>", unsafe_allow_html=True)
    st.subheader("Manual Zone Calibration")
    st.caption(
        "Left-click each zone corner in order. After three or more points, the preview below "
        "will close the polygon automatically. Use Reset Drawing if you want to start over."
    )

    canvas_result = st_canvas(
        fill_color="rgba(239, 68, 68, 0.20)",
        stroke_width=2,
        stroke_color="#f87171",
        background_image=background,
        update_streamlit=True,
        height=canvas_h,
        width=canvas_w,
        drawing_mode="point",
        display_toolbar=True,
        point_display_radius=5,
        key=f"manual-zone-canvas-{st.session_state.manual_zone_canvas_rev}",
    )

    extracted_points = _extract_polygon_points(
        canvas_result.json_data,
        scale_x=frame_w / canvas_w,
        scale_y=frame_h / canvas_h,
    )
    point_count = len(extracted_points)
    st.caption(f"Selected points: {point_count}")

    preview = _build_preview_frame(frame, extracted_points)
    st.image(
        cv2.cvtColor(preview, cv2.COLOR_BGR2RGB),
        channels="RGB",
        use_column_width=True,
        caption="Zone preview",
    )

    apply_col, reset_col, cancel_col = st.columns(3)
    if apply_col.button("Apply Zone", use_container_width=True):
        if point_count < 3:
            st.warning("Select at least three points to define a valid restricted zone.")
        else:
            st.session_state.manual_zone_points = extracted_points
            st.session_state.manual_zone_config_open = False
            st.session_state.zone_source = "MANUAL"
            st.success(f"Manual zone saved with {point_count} points.")

    if reset_col.button("Reset Drawing", use_container_width=True):
        st.session_state.manual_zone_canvas_rev += 1
        st.rerun()

    if cancel_col.button("Cancel", use_container_width=True):
        st.session_state.manual_zone_config_open = False
        st.rerun()

    st.markdown("</div>", unsafe_allow_html=True)


def _extract_polygon_points(json_data: dict | None, scale_x: float, scale_y: float) -> list[tuple[int, int]]:
    if not json_data:
        return []
    objects = json_data.get("objects") or []
    if not objects:
        return []

    point_objects = [_extract_point_object(obj) for obj in objects]
    point_objects = [point for point in point_objects if point is not None]
    if len(point_objects) >= 3:
        scaled_points = _scale_points(point_objects, scale_x, scale_y)
        return _normalize_polygon_points(scaled_points)

    for obj in reversed(objects):
        points = _extract_from_object(obj)
        if len(points) >= 3:
            scaled_points = _scale_points(points, scale_x, scale_y)
            return _normalize_polygon_points(scaled_points)
    return []


def _extract_from_object(obj: dict) -> list[tuple[float, float]]:
    obj_type = obj.get("type")
    if obj_type in {"circle", "point"}:
        point = _extract_point_object(obj)
        return [point] if point else []
    if obj_type == "polygon":
        return _extract_polygon_object_points(obj)
    if obj_type == "path":
        return _extract_path_object_points(obj)
    return []


def _extract_point_object(obj: dict) -> tuple[float, float] | None:
    left = obj.get("left")
    top = obj.get("top")
    if left is None or top is None:
        return None

    radius = obj.get("radius")
    if radius is not None:
        return (float(left) + float(radius), float(top) + float(radius))

    width = float(obj.get("width", 0.0))
    height = float(obj.get("height", 0.0))
    return (float(left) + width / 2.0, float(top) + height / 2.0)


def _extract_polygon_object_points(obj: dict) -> list[tuple[float, float]]:
    raw_points = obj.get("points") or []
    path_offset = obj.get("pathOffset") or {}
    offset_x = float(obj.get("left", 0.0)) - float(path_offset.get("x", 0.0))
    offset_y = float(obj.get("top", 0.0)) - float(path_offset.get("y", 0.0))
    points: list[tuple[float, float]] = []
    for point in raw_points:
        points.append(
            (
                float(point.get("x", 0.0)) + offset_x,
                float(point.get("y", 0.0)) + offset_y,
            )
        )
    return points


def _extract_path_object_points(obj: dict) -> list[tuple[float, float]]:
    path = obj.get("path") or []
    path_offset = obj.get("pathOffset") or {}
    offset_x = float(obj.get("left", 0.0)) - float(path_offset.get("x", 0.0))
    offset_y = float(obj.get("top", 0.0)) - float(path_offset.get("y", 0.0))
    points: list[tuple[float, float]] = []
    for segment in path:
        if not isinstance(segment, Iterable):
            continue
        command = segment[0]
        if command not in {"M", "L"} or len(segment) < 3:
            continue
        points.append((float(segment[1]) + offset_x, float(segment[2]) + offset_y))
    return _dedupe_points(points)


def _dedupe_points(points: list[tuple[float, float]]) -> list[tuple[float, float]]:
    deduped: list[tuple[float, float]] = []
    for point in points:
        if not deduped or point != deduped[-1]:
            deduped.append(point)
    if len(deduped) > 1 and deduped[0] == deduped[-1]:
        deduped.pop()
    return deduped


def _scale_points(
    points: list[tuple[float, float]],
    scale_x: float,
    scale_y: float,
) -> list[tuple[int, int]]:
    return [
        (int(round(x * scale_x)), int(round(y * scale_y)))
        for x, y in points
    ]


def _normalize_polygon_points(points: list[tuple[int, int]]) -> list[tuple[int, int]]:
    if len(points) < 3:
        return points

    unique_points: list[tuple[int, int]] = []
    seen: set[tuple[int, int]] = set()
    for point in points:
        if point in seen:
            continue
        seen.add(point)
        unique_points.append(point)

    if len(unique_points) < 3:
        return unique_points

    center_x = sum(x for x, _ in unique_points) / len(unique_points)
    center_y = sum(y for _, y in unique_points) / len(unique_points)
    return sorted(
        unique_points,
        key=lambda pt: np.arctan2(pt[1] - center_y, pt[0] - center_x),
    )


def _build_preview_frame(frame, points: list[tuple[int, int]]):
    preview = frame.copy()
    if len(points) >= 3:
        polygon = np.array(points, dtype=np.int32)
        overlay = preview.copy()
        cv2.fillPoly(overlay, [polygon], (50, 50, 220))
        cv2.addWeighted(overlay, 0.20, preview, 0.80, 0.0, preview)
        cv2.polylines(preview, [polygon], True, (120, 120, 255), 3)

    for idx, (x, y) in enumerate(points, start=1):
        cv2.circle(preview, (x, y), 8, (120, 120, 255), -1)
        cv2.circle(preview, (x, y), 10, (255, 255, 255), 2)
        cv2.putText(
            preview,
            str(idx),
            (x + 12, y - 12),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.65,
            (240, 248, 255),
            2,
            cv2.LINE_AA,
        )
    return preview
