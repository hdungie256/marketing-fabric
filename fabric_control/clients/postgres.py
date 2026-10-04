import json
import os
from typing import Any


def connect():
    import psycopg

    return psycopg.connect(os.environ["SERVING_DB_DSN"], autocommit=True)


def start_run(run_id: str, job_id: str, event_id: str | None, scope: dict[str, Any]) -> None:
    with connect() as conn:
        conn.execute(
            """
            INSERT INTO ops.runs (run_id, job_id, event_id, scope, status, started_at)
            VALUES (%s, %s, %s, %s, 'running', now())
            ON CONFLICT (run_id) DO UPDATE SET
                status = 'running', started_at = now(), ended_at = NULL, rows_in = NULL,
                rows_out = NULL, failing_step = NULL, delta_version = NULL
            """,
            (run_id, job_id, event_id, json.dumps(scope)),
        )


def end_run(
    run_id: str,
    status: str,
    rows_in: int | None,
    rows_out: int | None,
    failing_step: str | None,
    delta_version: int | None,
) -> None:
    with connect() as conn:
        conn.execute(
            """
            UPDATE ops.runs SET status = %s, ended_at = now(), rows_in = %s, rows_out = %s,
                failing_step = %s, delta_version = %s
            WHERE run_id = %s
            """,
            (status, rows_in, rows_out, failing_step, delta_version, run_id),
        )


def add_alert(run_id: str, job_id: str, severity: str, message: str) -> None:
    with connect() as conn:
        conn.execute(
            "INSERT INTO ops.alerts (run_id, job_id, severity, message) VALUES (%s, %s, %s, %s)",
            (run_id, job_id, severity, message),
        )
