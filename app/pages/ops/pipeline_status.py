"""Pipeline Status page (Stories 7.1, 7.4; FR-23, FR-26, UX-DR33, UX-DR41). Home page of UG06."""

from __future__ import annotations

from datetime import UTC, datetime

import streamlit as st

from app.services import pipeline_status as ps
from app.shell import banner_slot, empty_state, fmt_count, fmt_time, session, table
from app.shell.components.status_chip import status_chip
from app.shell.format import DASH, app_tz
from app.shell.roles import ROLES

CHIPS = {"queued": "neutral", "running": "info", "success": "success", "failed": "danger", "gated": "warning"}
REFRESH_SECONDS = 5
BROKEN = ("failed", "gated")
ALL = "Whole pipeline"
RELOAD_STARTED = "_reload_started"
RELOAD_WAIT_SECONDS = 120  # poll this long after Confirm; ops.runs gets a row only once Airflow starts the task


def load():
    with ps.connect(ROLES[session.role()]) as conn:
        return ps.read(conn)


def fmt_last_run(value) -> str:
    """HH:MM for a run started today, "Oct 22 12:28" for an older one, so an old failure does not read as today's."""
    if fmt_time(value) == DASH:
        return DASH
    local = (value if value.tzinfo else value.replace(tzinfo=UTC)).astimezone(app_tz())
    return local.strftime("%H:%M" if local.date() == datetime.now(app_tz()).date() else "%b %d %H:%M")


def reload_waiting() -> tuple[str, str, datetime] | None:
    """(source, run_id, started_at) of a reload started from this page in the last RELOAD_WAIT_SECONDS."""
    started = st.session_state.get(RELOAD_STARTED)
    if started and (datetime.now(UTC) - started[2]).total_seconds() < RELOAD_WAIT_SECONDS:
        return started
    return None


def polling(runs) -> bool:
    return ps.is_active(runs) or reload_waiting() is not None


def render_runs(latest) -> None:
    header = st.columns([4, 2, 1, 2, 2])
    for column, label in zip(header, ["Job", "Last run", "Duration", "Rows in → out", "Status"], strict=True):
        column.caption(label)
    for row in latest.itertuples():
        job, last, duration, rows, status = st.columns([4, 2, 1, 2, 2])
        job.markdown(f"`{row.job_id}`")
        if row.status in BROKEN:
            job.caption(f"Failed at {row.failing_step or 'unknown step'} — {row.cause or 'no alert recorded'}")
        last.markdown(fmt_last_run(row.started_at))
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
    st.session_state[RELOAD_STARTED] = (source or ALL, run_id, datetime.now(UTC))
    st.rerun()  # restart so the status list polls until the run shows up


def failed_source(runs) -> str | None:
    """The source whose ingest run failed or was gated most recently, so Reload targets it by default."""
    latest = ps.latest_runs(runs).sort_values("started_at", ascending=False)
    broken = latest[latest["job_id"].str.startswith("ingest/") & latest["status"].isin(BROKEN)]
    return None if broken.empty else broken["job_id"].iloc[0].split("/", 1)[1]


def render_reload(runs) -> None:
    st.subheader("Reload")
    options = [ALL, *ps.sources(runs)]
    choice = st.selectbox("Source", options, index=options.index(failed_source(runs) or ALL), key="reload-source")
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
    latest = latest.sort_values("status", key=lambda s: ~s.isin(BROKEN), kind="stable")  # broken steps first
    broken = latest[latest["status"].isin(BROKEN)]
    if not broken.empty:
        with banner_slot():
            st.warning(f"{len(broken)} step(s) failed or gated. Dependent pages keep their previous values.")
    st.subheader("Sources & steps")
    waiting = reload_waiting()
    if waiting:
        source, run_id, started = waiting
        newer = runs[runs["started_at"] >= started]
        if source != ALL:
            newer = newer[newer["job_id"] == f"ingest/{source}"]
        if newer.empty:
            target = "the whole pipeline" if source == ALL else source
            st.info(f"Reload of {target} sent to Airflow (run {run_id}). Its steps appear here once they start.")
    if st.query_params.get("status") == "failed":
        st.caption("Filtered to failed runs (from the alert indicator).")
        latest = broken
    if latest.empty:
        empty_state("No failed or gated runs now.", "Every source loaded on its last run.")
    else:
        render_runs(latest)
    st.subheader("Load reconciliation")
    if reconciliation.empty:
        empty_state("No source loads reconciled yet.")
    else:
        last = reconciliation.sort_values("checked_at").groupby("dataset_id").tail(1).sort_values("dataset_id")
        table(last[["dataset_id", "source_rows", "raw_rows", "baseline_rows", "passed", "reason", "checked_at"]])
    render_performance(runs, timings)
    active = polling(runs)
    if active:
        st.caption(f"Auto-refreshes every {REFRESH_SECONDS}s while a run is active.")
    if was_active and not active:
        st.rerun()  # drop the refresh timer once nothing is running (UX-DR41)


def render() -> None:
    runs = load()[0]
    active = polling(runs)
    st.fragment(run_every=REFRESH_SECONDS if active else None)(section)(active)
    if not runs.empty:
        render_reload(runs)  # outside the auto-refreshing fragment so the confirm dialog stays open
