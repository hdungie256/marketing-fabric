"""Pipeline Status page (Story 7.1, FR-23, UX-DR33, UX-DR41). Home page of UG06."""

from __future__ import annotations

import streamlit as st

from app.services import pipeline_status as ps
from app.shell import banner_slot, empty_state, fmt_count, fmt_time, session, table
from app.shell.components.status_chip import status_chip
from app.shell.roles import ROLES

CHIPS = {"queued": "neutral", "running": "info", "success": "success", "failed": "danger", "gated": "warning"}
REFRESH_SECONDS = 5


def load():
    with ps.connect(ROLES[session.role()]) as conn:
        return ps.read(conn)


def render_runs(latest) -> None:
    header = st.columns([4, 1, 1, 2, 2])
    for column, label in zip(header, ["Job", "Last run", "Duration", "Rows in → out", "Status"], strict=True):
        column.caption(label)
    for row in latest.itertuples():
        job, last, duration, rows, status = st.columns([4, 1, 1, 2, 2])
        job.markdown(f"`{row.job_id}`")
        if row.status in ("failed", "gated"):
            job.caption(f"Failed at {row.failing_step or 'unknown step'} — {row.cause or 'no alert recorded'}")
        last.markdown(fmt_time(row.started_at))
        duration.markdown(ps.fmt_duration(row.duration_s))
        rows.markdown(f"{fmt_count(row.rows_in)} → {fmt_count(row.rows_out)}")
        with status:
            status_chip(CHIPS.get(row.status, "neutral"), row.status)


def render_event(runs, event_id: str) -> None:
    chosen, elapsed = ps.event_runs(runs, event_id)
    st.subheader(f"Event {event_id}")
    if chosen.empty:
        empty_state(f"No runs recorded for event {event_id} yet.")
        return
    left, right = st.columns([3, 1])
    left.markdown(f"{ps.fmt_duration(elapsed)} elapsed · 2:00 target")
    with right:
        if elapsed is not None and elapsed > ps.TARGET_SECONDS:
            status_chip("warning", "Over 2 min target")
    render_runs(ps.latest_runs(chosen))


def section(was_active: bool) -> None:
    runs, alerts, reconciliation = load()
    if runs.empty:
        empty_state("No pipeline runs yet.", "Runs appear after bootstrap starts full_refresh.")
        return
    event_id = st.query_params.get("event_id")
    if event_id:
        render_event(runs, event_id)
    latest = ps.latest_runs(runs, alerts)
    broken = latest[latest["status"].isin(["failed", "gated"])]
    if not broken.empty:
        with banner_slot():
            st.warning(f"{len(broken)} step(s) failed or gated. Dependent pages keep their previous values.")
    st.subheader("Sources & steps")
    render_runs(latest)
    st.subheader("Load reconciliation")
    if reconciliation.empty:
        empty_state("No source loads reconciled yet.")
    else:
        last = reconciliation.sort_values("checked_at").groupby("dataset_id").tail(1).sort_values("dataset_id")
        table(last[["dataset_id", "source_rows", "raw_rows", "baseline_rows", "passed", "reason", "checked_at"]])
    active = ps.is_active(runs)
    if active:
        st.caption(f"Auto-refreshes every {REFRESH_SECONDS}s while a run is active.")
    if was_active and not active:
        st.rerun()  # drop the refresh timer once nothing is running (UX-DR41)


def render() -> None:
    runs, _, _ = load()
    active = ps.is_active(runs)
    st.fragment(run_every=REFRESH_SECONDS if active else None)(section)(active)
