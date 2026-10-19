"""Pipeline Status reads (Story 7.1, FR-23). Reads only generated ops_v views as the viewer's own login."""

from __future__ import annotations

import os
from datetime import UTC, datetime
from typing import Any

import pandas as pd
import psycopg

from app.services.exception_triage import read_view
from app.shell.roles import Role

TARGET_SECONDS = 120  # NFR-4: partial refresh under 2 minutes
ACTIVE = ("queued", "running")


def connect(role: Role) -> psycopg.Connection:
    return psycopg.connect(
        host=os.environ.get("DB_HOST", "postgresql"),
        port=int(os.environ.get("DB_PORT", "5432")),
        dbname="serving",
        user=role.db_user,
        password=os.environ[role.password_env],
        autocommit=True,
        options="-c default_transaction_read_only=on",
    )


VIEWS = ("ops_v.runs", "ops_v.alerts", "ops_v.load_reconciliation", "ops_v.page_timings")


def read(conn: Any) -> tuple[pd.DataFrame, ...]:
    """runs, alerts, load_reconciliation, page_timings."""
    return tuple(read_view(conn, view) for view in VIEWS)


def seconds(started: Any, ended: Any, now: datetime) -> float | None:
    if started is None or pd.isna(started):
        return None
    end = now if ended is None or pd.isna(ended) else ended
    return (end - started).total_seconds()


def latest_runs(runs: pd.DataFrame, alerts: pd.DataFrame | None = None, now: datetime | None = None) -> pd.DataFrame:
    """Last run per job with duration and, for failed or gated runs, the cause from its latest alert ("" if none)."""
    now = now or datetime.now(UTC)
    if runs.empty:
        return runs.assign(duration_s=[], cause=[])
    latest = runs.sort_values("started_at").groupby("job_id").tail(1).sort_values("job_id")
    causes = {}
    if alerts is not None and not alerts.empty:
        causes = alerts.sort_values("raised_at").groupby("run_id")["message"].last().to_dict()
    return latest.assign(
        duration_s=[seconds(s, e, now) for s, e in zip(latest["started_at"], latest["ended_at"], strict=True)],
        cause=[
            causes.get(r, "") if st in ("failed", "gated") else ""
            for r, st in zip(latest["run_id"], latest["status"], strict=True)
        ],
    ).reset_index(drop=True)


def is_active(runs: pd.DataFrame) -> bool:
    return not runs.empty and runs["status"].isin(ACTIVE).any()


def event_runs(runs: pd.DataFrame, event_id: str, now: datetime | None = None) -> tuple[pd.DataFrame, float | None]:
    """Runs of one change event in start order, plus elapsed seconds from the first start to the last end (or now)."""
    now = now or datetime.now(UTC)
    chosen = runs[runs["event_id"] == event_id].sort_values("started_at")
    if chosen.empty:
        return chosen, None
    still_running = chosen["status"].isin(ACTIVE).any()
    end = None if still_running else chosen["ended_at"].max()
    return chosen.reset_index(drop=True), seconds(chosen["started_at"].min(), end, now)


def fmt_duration(value: float | None) -> str:
    if value is None or pd.isna(value):
        return "—"
    minutes, secs = divmod(int(round(value)), 60)
    return f"{minutes}:{secs:02d}"


FULL_REFRESH_TARGET_SECONDS = 600  # NFR-4: full refresh under 10 minutes
PAGE_TARGET_MS = 3000  # NFR-4: analytics page responds in under 3 seconds
# Open alerts are failures whose job has not run successfully since: pipeline failures for UG06, quality gates for UG05.
ALERT_STATUS = {"UG06": "failed", "UG05": "gated"}


def alert_count(runs: pd.DataFrame, role: str) -> int:
    status = ALERT_STATUS.get(role)
    if status is None or runs.empty:
        return 0
    latest = runs.sort_values("started_at").groupby("job_id").tail(1)
    return int((latest["status"] == status).sum())


def dag_run_id(run_id: str) -> str:
    return run_id.rsplit(":", 1)[0]


def last_full_refresh_seconds(runs: pd.DataFrame, now: datetime | None = None) -> float | None:
    """Wall time of the latest full_refresh: first job start to last job end of the newest DAG run with no event."""
    full = runs[runs["event_id"].isna()]
    if full.empty:
        return None
    full = full.assign(dag_run=full["run_id"].map(dag_run_id))
    latest = full[full["dag_run"] == full.sort_values("started_at")["dag_run"].iloc[-1]]
    active = latest["status"].isin(ACTIVE).any()
    return seconds(latest["started_at"].min(), None if active else latest["ended_at"].max(), now or datetime.now(UTC))


def event_latencies(runs: pd.DataFrame, now: datetime | None = None) -> pd.DataFrame:
    """Partial refresh latency per change event (FR-26).

    ponytail: measured from the first job start, not the event's emitted_at; switch when Epic 8 records events."""
    events = runs["event_id"].dropna().unique()
    rows = [(event_id, event_runs(runs, event_id, now)[1]) for event_id in events]
    return pd.DataFrame(rows, columns=["event_id", "seconds"])


def page_percentiles(timings: pd.DataFrame) -> pd.DataFrame:
    if timings.empty:
        return pd.DataFrame(columns=["page", "p50_ms", "p95_ms", "samples"])
    ms = timings.assign(ms=timings["ms"].astype(float)).groupby("page")["ms"]
    out = pd.DataFrame({"p50_ms": ms.quantile(0.5), "p95_ms": ms.quantile(0.95), "samples": ms.size()})
    return out.reset_index()


def sources(runs: pd.DataFrame) -> list[str]:
    """Reloadable sources: the <source> of every ingest/<source> job seen in ops.runs."""
    return sorted({job.split("/", 1)[1] for job in runs["job_id"] if job.startswith("ingest/")})


def reload(source: str | None) -> str:
    """Start reload_source for one source, or full_refresh when source is None (FR-24). Returns the DAG run id."""
    import fabric_control

    if source is None:
        return fabric_control.trigger("full_refresh", {})
    return fabric_control.trigger("reload_source", {"source": source})
