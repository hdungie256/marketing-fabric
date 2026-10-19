"""Pipeline Status page (Stories 7.1, 7.4; FR-23, FR-26, UX-DR33, UX-DR41). Home page of UG06."""

from __future__ import annotations

import streamlit as st

from app.services import pipeline_status as ps
from app.shell import banner_slot, empty_state, fmt_count, fmt_time, session, table, toast
from app.shell.components.status_chip import status_chip
from app.shell.roles import ROLES

CHIPS = {"queued": "neutral", "running": "info", "success": "success", "failed": "danger", "gated": "warning"}
REFRESH_SECONDS = 5
BROKEN = ("failed", "gated")
ALL = "Whole pipeline"


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
        if row.status in BROKEN:
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


def measure(label: str, value: str, over: bool, target: str) -> None:
    left, mid, right = st.columns([4, 2, 2])
    left.markdown(label)
    mid.markdown(f"{value} · target {target}")
    with right:
        status_chip("warning" if over else "success", "Over target" if over else "Within target")


def render_performance(runs, timings) -> None:
    st.subheader("Performance")
    full = ps.last_full_refresh_seconds(runs)
    if full is not None:
        measure("Last full refresh", ps.fmt_duration(full), full > ps.FULL_REFRESH_TARGET_SECONDS, "10:00")
    for row in ps.event_latencies(runs).itertuples():
        measure(
            f"Partial refresh `{row.event_id}`", ps.fmt_duration(row.seconds), row.seconds > ps.TARGET_SECONDS, "2:00"
        )
    for row in ps.page_percentiles(timings).itertuples():
        over = row.p95_ms > ps.PAGE_TARGET_MS
        value = f"p50 {row.p50_ms / 1000:.2f}s · p95 {row.p95_ms / 1000:.2f}s ({row.samples} views)"
        measure(f"Page `{row.page}`", value, over, "3s")
    if full is None and timings.empty:
        empty_state("No timings recorded yet.")


PENDING = "_reload_pending"


def start_reload(source: str | None) -> None:
    try:
        run_id = ps.reload(source)
    except Exception as e:
        missing = getattr(e, "status", None) == 404
        st.error(
            "Reload did not start: the DAG is not deployed in Airflow." if missing else f"Reload did not start: {e}"
        )
        return
    toast(f"Reload started · {run_id}", "success")


def render_reload(runs) -> None:
    st.subheader("Reload")
    choice = st.selectbox("Source", [ALL, *ps.sources(runs)], key="reload-source")
    if st.button("Reload source" if choice != ALL else "Reload all", key="reload-start"):
        st.session_state[PENDING] = choice
    pending = st.session_state.get(PENDING)
    if pending is None:
        return
    st.warning(f"Reload {pending.lower() if pending == ALL else pending}? Dependent jobs rerun after it.")
    confirm, cancel = st.columns(2)
    if confirm.button("Confirm reload", type="primary", key="reload-confirm"):
        del st.session_state[PENDING]
        start_reload(None if pending == ALL else pending)
    elif cancel.button("Cancel", key="reload-cancel"):
        del st.session_state[PENDING]
        st.rerun()


def section(was_active: bool) -> None:
    runs, alerts, reconciliation, timings = load()
    if runs.empty:
        empty_state("No pipeline runs yet.", "Runs appear after bootstrap starts full_refresh.")
        return
    event_id = st.query_params.get("event_id")
    if event_id:
        render_event(runs, event_id)
    latest = ps.latest_runs(runs, alerts)
    broken = latest[latest["status"].isin(BROKEN)]
    if not broken.empty:
        with banner_slot():
            st.warning(f"{len(broken)} step(s) failed or gated. Dependent pages keep their previous values.")
    st.subheader("Sources & steps")
    if st.query_params.get("status") == "failed":
        st.caption("Filtered to failed runs (from the alert indicator).")
        latest = broken
    render_runs(latest)
    st.subheader("Load reconciliation")
    if reconciliation.empty:
        empty_state("No source loads reconciled yet.")
    else:
        last = reconciliation.sort_values("checked_at").groupby("dataset_id").tail(1).sort_values("dataset_id")
        table(last[["dataset_id", "source_rows", "raw_rows", "baseline_rows", "passed", "reason", "checked_at"]])
    render_performance(runs, timings)
    active = ps.is_active(runs)
    if active:
        st.caption(f"Auto-refreshes every {REFRESH_SECONDS}s while a run is active.")
    if was_active and not active:
        st.rerun()  # drop the refresh timer once nothing is running (UX-DR41)


def render() -> None:
    runs = load()[0]
    active = ps.is_active(runs)
    st.fragment(run_every=REFRESH_SECONDS if active else None)(section)(active)
    if not runs.empty:
        render_reload(runs)  # outside the auto-refreshing fragment so the confirm dialog stays open
