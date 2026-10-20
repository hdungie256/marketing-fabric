"""Change History page (Story 8.6, BR16): what one source change refreshed and which values it changed."""

from __future__ import annotations

import logging
from datetime import UTC

import pandas as pd
import psycopg
import streamlit as st

import fabric_control
from app.services import change_history as ch
from app.services import pipeline_status
from app.services.exception_triage import read_view
from app.shell import (
    Filter,
    NotPermittedError,
    current_source,
    empty_state,
    filter_bar,
    fmt_date,
    fmt_money,
    fmt_time,
    session,
    table,
)
from app.shell.components.definition_dialog import definition_dialog
from app.shell.components.lineage_graph import lineage_flow
from app.shell.components.spend_edit import PAGE_TITLE
from app.shell.data_source import data_mode
from app.shell.format import DASH, app_tz
from app.shell.roles import ROLES
from fabric_control.glossary import load_terms

log = logging.getLogger(__name__)
EMPTY = "No source changes recorded yet."
ALL = "All campaigns"
HEADERS = ["Metric", "", "Level", "Shown on", "Old", "New", "Change"]


def load(role: str) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    with pipeline_status.connect(ROLES[role]) as conn:
        return tuple(read_view(conn, v) for v in ("ops_v.source_events", "ops_v.runs", "ops_v.metric_change_log"))


def _read(dataset_id: str) -> pd.DataFrame | None:
    try:
        return current_source().read(dataset_id)
    except NotPermittedError:
        return None  # the viewer cannot read it: skipped from the kept count


def _money(value) -> str:
    return fmt_money(value, places=2)


def _signed(value) -> str:
    if pd.isna(value):
        return DASH
    return ("+" if value > 0 else "\u2212" if value < 0 else "") + _money(abs(value))  # U+2212 minus, as the spec


def _saved(value) -> str:
    if pd.isna(value):
        return DASH
    value = value if value.tzinfo else value.replace(tzinfo=UTC)
    return f"{fmt_date(value.astimezone(app_tz()))} {fmt_time(value)}"  # date in APP_TZ too, not UTC


def _summary(event: dict, rows: pd.DataFrame, terms: dict) -> None:
    event = ch.parse_event(event)
    marts = [a["dataset_id"] for a in fabric_control.affected_by(event) if a["dataset_id"].startswith("mart_")]
    # Metric columns: glossary-defined ones plus the columns the change log tracks.
    metrics = {
        d: sorted(
            {t["column"] for t in terms.values() if t["dataset_id"] == d}
            | {c for s, c in ch.MEANING if s == ch.short_name(d)}
        )
        for d in marts
    }
    m, latest = ch.kept({d: _read(d) for d in marts}, metrics, event["emitted_at"])
    st.markdown(f"**{len(rows)} metrics changed** · {m} unchanged kept refresh time {fmt_time(latest)}")
    campaign = ch.first(event["keys"].get("campaign_id"))
    st.caption(f"{campaign} only. Other campaigns and datasets not downstream of spend were not refreshed.")


def _changed_values(rows: pd.DataFrame, campaign: str) -> None:
    st.subheader("Changed values")
    if rows.empty:
        st.caption("No values changed for this event.")
        return
    st.caption(f"{campaign}. Select ⓘ for the metric definition.")
    widths = [3, 1, 3, 2, 2, 2, 2]
    for column, title in zip(st.columns(widths), HEADERS, strict=True):
        column.caption(title)
    for i, row in enumerate(rows.to_dict("records")):
        metric, info, level, page, old, new, change = st.columns(widths)
        metric.markdown(row["metric"])
        if row["info_term"] and info.button("ⓘ", key=f"change-info-{i}"):
            definition_dialog(row["info_term"])
        level.markdown(row["level"])
        if not row["page"]:
            page.markdown(DASH)
        elif page.button(PAGE_TITLE.get(row["page"], row["page"]), key=f"change-page-{i}", type="tertiary"):
            session.request_redirect(row["page"])
            st.rerun()
        old.markdown(_money(row["old"]))
        new.markdown(_money(row["new"]))
        change.markdown(_signed(row["change"]))


def render() -> None:
    if data_mode() == "fixture":
        empty_state(EMPTY)
        return
    try:
        events, runs, change_log = load(session.role())
    except psycopg.Error:
        log.warning("change history: could not read ops views", exc_info=True)
        empty_state(EMPTY)
        return
    if events.empty:
        empty_state(EMPTY)
        return
    terms = load_terms()

    st.subheader("Source changes")
    st.caption("Most recent first. Select a change to see what it updated.")
    listed = ch.event_table(events, runs, change_log)
    campaigns = sorted(listed["campaign_id"].dropna().unique())
    chosen = filter_bar("change_history", [Filter("campaign", "Campaign", [ALL, *campaigns])])["campaign"]
    if chosen != ALL:
        listed = listed[listed["campaign_id"] == chosen]
    ids = list(listed["event_id"])
    wanted = st.query_params.get("event_id")
    event_id = st.selectbox(
        "Change", ids, index=ids.index(wanted) if wanted in ids else 0, key="change_event",
        format_func=lambda e: listed.set_index("event_id").loc[e, "change"],
    )  # fmt: skip
    shown = listed.assign(
        saved_at=listed["saved_at"].map(_saved),
        refresh_seconds=listed["refresh_seconds"].map(pipeline_status.fmt_duration),
    ).rename(
        columns={
            "saved_at": "Saved at", "change": "Change", "campaign_id": "Campaign", "datasets": "Datasets refreshed",
            "values_changed": "Values changed", "refresh_seconds": "Refresh time",
        }
    )  # fmt: skip
    table(
        shown.drop(columns=["event_id"]),
        formats={"Datasets refreshed": "count", "Values changed": "count"},
        highlight=lambda r: shown.loc[r.name, "event_id"] == event_id,
    )
    if event_id is None:
        return
    event = events[events["event_id"] == event_id].iloc[0].to_dict()
    rows = ch.changed_values(change_log, event, terms)
    _summary(event, rows, terms)

    st.subheader("How the change flowed")
    lineage_flow(ch.flow(event, runs, change_log))
    rest = ch.not_downstream(event)
    if rest:
        more = f" and {len(rest) - 5} more" if len(rest) > 5 else ""
        st.caption(f"Not downstream of spend, not refreshed: {', '.join(rest[:5])}{more}")

    _changed_values(rows, ch.first(ch.parse_event(event)["keys"].get("campaign_id")))
