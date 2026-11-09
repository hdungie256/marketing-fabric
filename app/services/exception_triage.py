"""UG05 triage reads and writes (Story 3.4, FR-9).

Reads touch only generated `*_v` views (same rule as PgSource); triage
writes go through the `app_writer` login. Connections are created by the
page and passed in, so unit tests use fakes.
"""

from __future__ import annotations

import os
from typing import Any

import pandas as pd
import psycopg

STATUSES = ("new", "seen", "accepted")
RESOLVED = "resolved at source"


def connect_reader() -> psycopg.Connection:
    return psycopg.connect(
        host=os.environ.get("DB_HOST", "postgresql"),
        port=int(os.environ.get("DB_PORT", "5432")),
        dbname="serving",
        user=os.environ.get("DATA_STEWARD_DB_USER", "data_steward"),
        password=os.environ["DATA_STEWARD_DB_PASSWORD"],
        autocommit=True,
        options="-c default_transaction_read_only=on",
    )


def connect_writer() -> psycopg.Connection:
    return psycopg.connect(
        host=os.environ.get("DB_HOST", "postgresql"),
        port=int(os.environ.get("DB_PORT", "5432")),
        dbname="serving",
        user="app_writer",
        password=os.environ["APP_WRITER_DB_PASSWORD"],
        autocommit=True,
    )


def read_view(conn: Any, view: str) -> pd.DataFrame:
    schema, _, table = view.partition(".")
    if not schema.endswith("_v") or not table:
        raise ValueError(f"{view}: only generated *_v views may be read")
    cursor = conn.execute(f'SELECT * FROM "{schema}"."{table}"')
    return pd.DataFrame(cursor.fetchall(), columns=[d.name for d in cursor.description])


def scoreboard(dq: pd.DataFrame) -> pd.DataFrame:
    """Latest score per dataset plus its failing rules (rule_id + severity)."""
    if dq.empty:
        return pd.DataFrame(columns=["dataset_id", "score_pct", "status", "failing"])
    latest = dq.sort_values("checked_at").groupby("dataset_id").tail(1)
    failing = (
        dq.merge(latest[["dataset_id", "checked_at"]], on=["dataset_id", "checked_at"])
        .query("passed == False")
        .groupby("dataset_id")[["rule_id", "severity"]]
        .apply(lambda g: "; ".join(f"{r.rule_id} ({r.severity})" for r in g.itertuples()), include_groups=False)
    )
    out = latest[["dataset_id", "score_pct", "status"]].merge(failing.rename("failing"), on="dataset_id", how="left")
    out["failing"] = out["failing"].fillna("")
    return out.sort_values("dataset_id").reset_index(drop=True)


def with_status(exceptions: pd.DataFrame, statuses: pd.DataFrame) -> pd.DataFrame:
    """Join triage statuses; default new; missing exceptions stay as resolved."""
    merged = exceptions.merge(statuses[["exception_id", "status"]], on="exception_id", how="left")
    merged["status"] = merged["status"].fillna("new")
    orphan = statuses[~statuses["exception_id"].isin(set(exceptions["exception_id"]))].copy()
    if not orphan.empty:
        orphan["status"] = RESOLVED
        for column in exceptions.columns:
            if column not in orphan.columns:
                orphan[column] = None
        merged = pd.concat([merged, orphan[merged.columns]], ignore_index=True)
    return merged


def coupon_status_counts(exceptions: pd.DataFrame) -> dict[str, int]:
    """Coupon status of coupon_plan_mismatch lines, read from detail; for reference only, never a criterion (R17)."""
    if "detail" not in exceptions:
        return {}
    detail = exceptions.loc[exceptions["class"].eq("coupon_plan_mismatch"), "detail"]
    found = detail.str.extract(r"coupon_status=([^;]+)", expand=False).dropna()
    return {status: int(count) for status, count in found.value_counts().items()}


def mark_status(conn: Any, exception_ids: list[str], status: str, by: str, known_ids: set[str]) -> int:
    """Upsert triage statuses. Only ids present in the mart may be marked."""
    if status not in ("seen", "accepted"):
        raise ValueError(f"{status}: triage status must be seen or accepted")
    unknown = sorted(set(exception_ids) - set(known_ids))
    if unknown:
        raise ValueError(f"{len(unknown)} ids resolved at source and cannot be marked")
    with conn.cursor() as cur:
        cur.executemany(
            "INSERT INTO app.exception_status (exception_id, status, updated_by)"
            " VALUES (%s, %s, %s)"
            " ON CONFLICT (exception_id) DO UPDATE"
            " SET status = EXCLUDED.status, updated_by = EXCLUDED.updated_by, updated_at = now()",
            [(eid, status, by) for eid in exception_ids],
        )
    return len(exception_ids)
