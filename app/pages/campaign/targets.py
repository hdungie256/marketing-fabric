import altair as alt
import pandas as pd
import streamlit as st

import fabric_control
from app.services import target_achievement as svc
from app.shell import (
    CAMPAIGN_COLORS,
    add_footnote,
    add_stale,
    current_in_flight,
    current_source,
    fmt_pct,
    freshness_badge,
    status_chip,
    table,
    watch,
)
from app.shell.badges import badge_stale, badge_synthetic

SUBTITLE = "How far each campaign got toward its own goal."
FOOTNOTE = "Stop below 70%, Continue from 100%. Goals were set after the fact for this demo."
CHIPS = {"continue": ("success", "Continue"), "adjust": ("warning", "Adjust"), "stop": ("danger", "Stop")}
# DESIGN.md danger-tint / warning-tint / success-tint
BANDS = [(0, 0.7, "#FBE7E6"), (0.7, 1.0, "#FCEEDC"), (1.0, svc.RULER_MAX, "#E5F3E9")]
ROW_H = 64
AXIS_H = 32
TEXT = "#1A1F29"


def ruler(df: pd.DataFrame) -> alt.LayerChart:
    d = df.assign(
        label=df["campaign_name"] + "\n" + df["goal"],
        at=df["achievement"].clip(upper=svc.RULER_MAX),
        pct=[fmt_pct(a) for a in df["achievement"]],
    )
    order = list(d["label"])
    y = alt.Y("label:N", sort=order, title=None, axis=alt.Axis(grid=False, domain=False, ticks=False, labelLimit=240))
    scale = alt.Scale(domain=[0, svc.RULER_MAX], nice=False)
    x = alt.X(
        "at:Q",
        title=None,
        scale=scale,
        axis=alt.Axis(orient="top", values=[0, 0.7, 1.0, svc.RULER_MAX], format=".0%", grid=False, domain=False),
    )
    bands = (
        alt.Chart(pd.DataFrame(BANDS, columns=["lo", "hi", "color"]))
        .mark_rect()
        .encode(x=alt.X("lo:Q", scale=scale), x2="hi:Q", color=alt.Color("color:N", scale=None))
    )
    lines = (
        alt.Chart(pd.DataFrame({"v": [0.7, 1.0]}))
        .mark_rule(strokeDash=[4, 4], color="#5B6472")
        .encode(x=alt.X("v:Q", scale=scale))
    )
    colors = alt.Scale(domain=list(d["campaign_id"]), range=[CAMPAIGN_COLORS[c] for c in d["campaign_id"]])
    points = (
        alt.Chart(d)
        .mark_circle(size=220, opacity=1)
        .encode(x=x, y=y, color=alt.Color("campaign_id:N", scale=colors, legend=None), tooltip=["detail"])
    )
    labels = alt.Chart(d).mark_text(dy=-16, color=TEXT, fontWeight="bold").encode(x=x, y=y, text="pct:N")
    return (bands + lines + points + labels).properties(height=alt.Step(ROW_H), width="container")


def chip_column(df: pd.DataFrame, stale: bool) -> None:
    st.container(height=AXIS_H, border=False)
    for recommendation in df["recommendation"]:
        with st.container(height=ROW_H, border=False, vertical_alignment="center"):
            variant, text = CHIPS[recommendation]
            status_chip(variant, text)
            if stale:
                badge_stale()


def table_view(df: pd.DataFrame) -> None:
    names = {t: fabric_control.term(t)["display_name"] for t in ("target_achievement", "allocated_spend")}
    shown = df.assign(goal_metric=[fabric_control.term(m)["display_name"] for m in df["target_metric"]])
    out = shown[
        [
            "campaign_id",
            "campaign_name",
            "goal_metric",
            "target_value",
            "actual",
            "achievement",
            "allocated_spend",
            "recommendation",
        ]
    ].rename(
        columns={
            "campaign_id": "Campaign",
            "goal_metric": "Goal metric",
            "target_value": "Target",
            "actual": "Actual",
            "achievement": names["target_achievement"],
            "allocated_spend": names["allocated_spend"],
            "recommendation": "Recommendation",
        }
    )
    out["Recommendation"] = out["Recommendation"].map(lambda r: CHIPS[r][1])
    table(
        out,
        dataset_id=svc.DATASET,
        campaign_col="Campaign",
        formats={
            "Target": "money",
            "Actual": "money",
            names["target_achievement"]: "pct",
            names["allocated_spend"]: "money",
        },
        info_terms={names["target_achievement"]: "target_achievement", names["allocated_spend"]: "allocated_spend"},
    )


def render() -> None:
    raw = svc.load(current_source())
    df = svc.rows(raw)
    state = fabric_control.status(svc.DATASET)
    stale = bool(state.get("stale"))
    if stale:
        add_stale(state.get("datasets", []))
    st.caption(SUBTITLE)
    badge_synthetic()
    shown = current_in_flight(None)
    freshness_badge(raw["_refreshed_at"].max(), svc.DATASET, shown)
    if shown:
        watch(None, shown)
    if st.toggle("Table view", key="targets_table_view"):
        table_view(df)
    else:
        chart_col, chip_col = st.columns([5, 1])
        with chart_col:
            st.altair_chart(ruler(df), use_container_width=True)
        with chip_col:
            chip_column(df, stale)
    add_footnote(FOOTNOTE)
