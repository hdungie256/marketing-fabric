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


def read(conn: Any) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    return read_view(conn, "ops_v.runs"), read_view(conn, "ops_v.alerts"), read_view(conn, "ops_v.load_reconciliation")


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
