"""ui/graphs.py — Altair-powered graphs view for SafeSight PPE Monitor."""

from __future__ import annotations

from pathlib import Path

import altair as alt
import pandas as pd
import streamlit as st

# ── Theme tokens (mirrors styles.py CSS variables) ────────────────────────────
_BG_CARD       = "#0d1626"
_TEXT_MAIN     = "#e5eefc"
_TEXT_MUTED    = "#93a4bd"
_BORDER        = "#1e2d45"
_ACCENT        = "#7dd3fc"   # sky-300 — matches --border-strong hue
_DANGER        = "#f87171"   # red-400
_WARN          = "#fb923c"   # orange-400
_SUCCESS       = "#34d399"   # emerald-400
_GRID          = "#111e30"

# Shared chart height — all charts use this so the dashboard feels uniform
_CHART_H = 300

# Per-worker colour ramp (cycles for many workers)
_WORKER_COLORS = [
    "#7dd3fc", "#34d399", "#fb923c", "#f87171",
    "#a78bfa", "#fbbf24", "#38bdf8", "#4ade80",
]

# ── Shared Altair theme config ────────────────────────────────────────────────

def _base_config() -> dict:
    """Return Altair config dict applied to every chart."""
    return {
        "background":   "transparent",
        "view":         {"stroke": "transparent", "fill": _BG_CARD},
        "axis": {
            "domainColor":    _BORDER,
            "gridColor":      _GRID,
            "tickColor":      _BORDER,
            "labelColor":     _TEXT_MUTED,
            "titleColor":     _TEXT_MUTED,
            "labelFont":      "Space Grotesk, sans-serif",
            "titleFont":      "Space Grotesk, sans-serif",
            "labelFontSize":  11,
            "titleFontSize":  12,
            "gridOpacity":    0.6,
        },
        "legend": {
            "labelColor":     _TEXT_MUTED,
            "titleColor":     _TEXT_MUTED,
            "labelFont":      "Space Grotesk, sans-serif",
            "titleFont":      "Space Grotesk, sans-serif",
            "labelFontSize":  11,
            "titleFontSize":  12,
        },
        "title": {
            "color":      _TEXT_MAIN,
            "font":       "Space Grotesk, sans-serif",
            "fontSize":   14,
            "fontWeight": 600,
            "anchor":     "start",
            "offset":     12,
        },
        "mark": {"tooltip": True},
    }


def _apply_theme(chart: alt.Chart) -> alt.Chart:
    return chart.configure(**_base_config())


# ── CSV loader ────────────────────────────────────────────────────────────────

@st.cache_data(show_spinner=False)
def load_violation_dataframe(csv_path: str, modified_time: float) -> pd.DataFrame:
    del modified_time  # used only as cache-bust key
    df = pd.read_csv(csv_path)
    if df.empty:
        return df

    df["timestamp_epoch"] = df["timestamp_epoch"].astype(int)
    df["worker_id"]       = df["worker_id"].astype(str)
    df["timestamp"]       = pd.to_datetime(df["timestamp_epoch"], unit="s")
    return df.sort_values("timestamp_epoch").reset_index(drop=True)


# ── Data builders ─────────────────────────────────────────────────────────────

def _violations_over_time(df: pd.DataFrame, window_seconds: int = 120) -> pd.DataFrame:
    """Violations per second for the last *window_seconds* of data."""
    latest = int(df["timestamp_epoch"].max())
    recent = df[df["timestamp_epoch"] >= latest - window_seconds].copy()
    if recent.empty:
        return pd.DataFrame(columns=["timestamp", "violations"])
    grouped = (
        recent.groupby("timestamp_epoch")
        .size()
        .reset_index(name="violations")
    )
    grouped["timestamp"] = pd.to_datetime(grouped["timestamp_epoch"], unit="s")
    return grouped[["timestamp", "violations"]]


def _worker_violation_counts(df: pd.DataFrame) -> pd.DataFrame:
    return (
        df.groupby("worker_id")
        .size()
        .reset_index(name="violations")
        .sort_values("violations", ascending=False)
        .reset_index(drop=True)
    )


def _cumulative_violations(df: pd.DataFrame) -> pd.DataFrame:
    grouped = (
        df.groupby("timestamp_epoch")
        .size()
        .reset_index(name="count")
        .sort_values("timestamp_epoch")
    )
    grouped["cumulative"] = grouped["count"].cumsum()
    grouped["timestamp"]  = pd.to_datetime(grouped["timestamp_epoch"], unit="s")
    return grouped[["timestamp", "cumulative"]]



# ── Individual Altair charts ──────────────────────────────────────────────────

def _chart_violations_over_time(df: pd.DataFrame) -> alt.Chart | None:
    """Gradient area + line chart for recent violation bursts."""
    data = _violations_over_time(df, window_seconds=120)
    if data.empty:
        return None

    nearest = alt.selection_point(
        nearest=True, on="mouseover", fields=["timestamp"], empty=False
    )

    base = alt.Chart(data).encode(
        x=alt.X(
            "timestamp:T",
            title="Time",
            axis=alt.Axis(format="%H:%M:%S", labelAngle=-30, tickCount=6),
        ),
        y=alt.Y(
            "violations:Q",
            title="Violations",
            scale=alt.Scale(domainMin=0, nice=True),
        ),
    )

    area = base.mark_area(
        line={"color": _ACCENT, "strokeWidth": 2},
        color=alt.Gradient(
            gradient="linear",
            stops=[
                alt.GradientStop(color=_ACCENT,               offset=1),
                alt.GradientStop(color="rgba(125,211,252,0)", offset=0),
            ],
            x1=0, x2=0, y1=1, y2=0,
        ),
        opacity=0.35,
        interpolate="monotone",
    )

    line   = base.mark_line(color=_ACCENT, strokeWidth=2, interpolate="monotone")

    points = base.mark_point(color=_ACCENT, filled=True, size=70).encode(
        opacity=alt.condition(nearest, alt.value(1), alt.value(0)),
        tooltip=[
            alt.Tooltip("timestamp:T",  title="Time",       format="%H:%M:%S"),
            alt.Tooltip("violations:Q", title="Violations"),
        ],
    ).add_params(nearest)

    rule = base.mark_rule(
        color=_BORDER, strokeWidth=1, strokeDash=[4, 4]
    ).encode(
        opacity=alt.condition(nearest, alt.value(0.8), alt.value(0))
    ).transform_filter(nearest)

    return (
        (area + line + points + rule)
        .properties(title="Violations — Last 2 Minutes", height=_CHART_H)
        .interactive()
    )



def _chart_cumulative(df: pd.DataFrame) -> alt.Chart | None:
    """Step-line cumulative violations over the full session."""
    data = _cumulative_violations(df)
    if data.empty:
        return None

    return (
        alt.Chart(data)
        .mark_area(
            interpolate="step-after",
            line={"color": _DANGER, "strokeWidth": 2},
            color=alt.Gradient(
                gradient="linear",
                stops=[
                    alt.GradientStop(color=_DANGER,               offset=1),
                    alt.GradientStop(color="rgba(248,113,113,0)", offset=0),
                ],
                x1=0, x2=0, y1=1, y2=0,
            ),
            opacity=0.25,
        )
        .encode(
            x=alt.X(
                "timestamp:T",
                title="Time",
                axis=alt.Axis(format="%H:%M", labelAngle=-30),
            ),
            y=alt.Y(
                "cumulative:Q",
                title="Cumulative Violations",
                scale=alt.Scale(domainMin=0, nice=True),
            ),
            tooltip=[
                alt.Tooltip("timestamp:T",  title="Time",        format="%H:%M:%S"),
                alt.Tooltip("cumulative:Q", title="Total So Far"),
            ],
        )
        .properties(title="Cumulative Violations (Session)", height=_CHART_H)
        .interactive()
    )


def _chart_worker_bars(df: pd.DataFrame) -> alt.Chart | None:
    """Horizontal bar chart ranked by most violations."""
    data = _worker_violation_counts(df)
    if data.empty:
        return None

    n       = len(data)
    colors  = (_WORKER_COLORS * ((n // len(_WORKER_COLORS)) + 1))[:n]
    c_scale = alt.Scale(domain=data["worker_id"].tolist(), range=colors)

    return (
        alt.Chart(data)
        .mark_bar(cornerRadiusTopRight=4, cornerRadiusBottomRight=4)
        .encode(
            x=alt.X(
                "violations:Q",
                title="Total Violations",
                scale=alt.Scale(domainMin=0, nice=True),
            ),
            y=alt.Y("worker_id:N", sort="-x", title="Worker ID",
                    axis=alt.Axis(labelLimit=120)),
            color=alt.Color("worker_id:N", scale=c_scale, legend=None),
            tooltip=[
                alt.Tooltip("worker_id:N",  title="Worker"),
                alt.Tooltip("violations:Q", title="Violations"),
            ],
        )
        .properties(title="Violations by Worker", height=max(_CHART_H, n * 38))
    )


def _chart_worker_timeline(df: pd.DataFrame) -> alt.Chart | None:
    """Tick / rug chart: each violation event plotted per worker over time."""
    if df.empty:
        return None

    worker_list = sorted(df["worker_id"].unique().tolist())
    n           = len(worker_list)
    colors      = (_WORKER_COLORS * ((n // len(_WORKER_COLORS)) + 1))[:n]
    c_scale     = alt.Scale(domain=worker_list, range=colors)
    selection   = alt.selection_point(fields=["worker_id"], bind="legend")

    return (
        alt.Chart(df)
        .mark_tick(thickness=2, size=18)
        .encode(
            x=alt.X(
                "timestamp:T",
                title="Time",
                axis=alt.Axis(format="%H:%M", labelAngle=-30),
            ),
            y=alt.Y("worker_id:N", title="Worker ID"),
            color=alt.Color("worker_id:N", scale=c_scale, title="Worker"),
            opacity=alt.condition(selection, alt.value(0.9), alt.value(0.12)),
            tooltip=[
                alt.Tooltip("worker_id:N", title="Worker"),
                alt.Tooltip("timestamp:T", title="Time", format="%H:%M:%S"),
            ],
        )
        .add_params(selection)
        .properties(
            title="Violation Timeline by Worker (click legend to isolate)",
            height=max(_CHART_H, n * 36),
        )
        .interactive()
    )


# ── Summary metric cards ──────────────────────────────────────────────────────

def _render_summary_metrics(df: pd.DataFrame) -> None:
    total        = len(df)
    n_workers    = df["worker_id"].nunique()
    duration_s   = int(df["timestamp_epoch"].max() - df["timestamp_epoch"].min())
    mins, secs   = divmod(duration_s, 60)
    duration_str = f"{mins}m {secs}s" if mins else f"{secs}s"
    top_worker   = df.groupby("worker_id").size().idxmax() if total else "—"

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Total Violations", total)
    c2.metric("Workers Tracked",  n_workers)
    c3.metric("Session Duration", duration_str)
    c4.metric("Most Violations",  f"Worker {top_worker}")


# ── Main entry point ──────────────────────────────────────────────────────────

def render_graphs_view(selected_csv_path: str | None) -> None:
    st.subheader("Violation Analytics")

    if not selected_csv_path:
        st.info("No CSV session available yet. Start monitoring to generate one.")
        return

    csv_path = Path(selected_csv_path)
    if not csv_path.exists():
        st.warning("Selected CSV file does not exist.")
        return

    df = load_violation_dataframe(str(csv_path), csv_path.stat().st_mtime)

    if df.empty:
        st.info("Selected CSV is empty. Run monitoring to generate violation events.")
        return

    st.caption(f"Source: `{csv_path.name}`")

    # ── Summary row ───────────────────────────────────────────────────────────
    _render_summary_metrics(df)
    st.write("")

    # ── Row 1: recent burst — full width ─────────────────────────────────────
    chart = _chart_violations_over_time(df)
    if chart:
        st.altair_chart(_apply_theme(chart), use_container_width=True)
    else:
        st.info("Not enough recent data yet.")

    st.write("")

    # ── Row 2: cumulative  +  worker bars ────────────────────────────────────
    col_c, col_d = st.columns(2, gap="large")

    with col_c:
        chart = _chart_cumulative(df)
        if chart:
            st.altair_chart(_apply_theme(chart), use_container_width=True)

    with col_d:
        chart = _chart_worker_bars(df)
        if chart:
            st.altair_chart(_apply_theme(chart), use_container_width=True)

    st.write("")

    # ── Row 3: full-width worker timeline ────────────────────────────────────
    chart = _chart_worker_timeline(df)
    if chart:
        st.altair_chart(_apply_theme(chart), use_container_width=True)
