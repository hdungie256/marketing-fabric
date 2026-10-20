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
                rows_out = NULL, failing_step = NULL, delta_version = NULL,
                delta_version_before = NULL
            """,
            (run_id, job_id, event_id, json.dumps(scope)),
        )


def insert_event(event: dict[str, Any], dag_run_id: str | None) -> None:
    with connect() as conn:
        conn.execute(
            """
            INSERT INTO ops.source_events (event_id, emitted_at, source, keys, source_version, dag_run_id)
            VALUES (%s, %s, %s, %s, %s, %s)
            """,
            (
                event["event_id"],
                event["emitted_at"],
                event["source"],
                json.dumps(event["keys"]),
                event["source_version"],
                dag_run_id,
            ),
        )


def end_run(
    run_id: str,
    status: str,
    rows_in: int | None,
    rows_out: int | None,
    failing_step: str | None,
    delta_version: int | None,
    delta_version_before: int | None = None,
) -> None:
    with connect() as conn:
        conn.execute(
            """
            UPDATE ops.runs SET status = %s, ended_at = now(), rows_in = %s, rows_out = %s,
                failing_step = %s, delta_version = %s, delta_version_before = %s
            WHERE run_id = %s
            """,
            (status, rows_in, rows_out, failing_step, delta_version, delta_version_before, run_id),
        )


def insert_metric_changes(run_id: str, event_id: str | None, dataset_id: str, changes: list[tuple]) -> None:
    rows = [(run_id, event_id, dataset_id, json.dumps(key), term_id, was, now) for key, term_id, was, now in changes]
    with connect() as conn, conn.cursor() as cursor:
        cursor.executemany(
            """
            INSERT INTO ops.metric_change_log
                (run_id, event_id, dataset_id, grain_key, term_id, old_value, new_value)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            """,
            rows,
        )


def add_alert(run_id: str, job_id: str, severity: str, message: str) -> None:
    with connect() as conn:
        conn.execute(
            "INSERT INTO ops.alerts (run_id, job_id, severity, message) VALUES (%s, %s, %s, %s)",
            (run_id, job_id, severity, message),
        )


def write_dq_results(
    run_id: str, dataset_id: str, scope: dict[str, Any], score_pct: float, status: str, rules: list[Any]
) -> None:
    rows = [
        (run_id, dataset_id, r.rule_id, r.severity, r.passed, r.detail, score_pct, status, json.dumps(scope))
        for r in rules
    ]
    with connect() as conn, conn.transaction():
        conn.execute("DELETE FROM ops.dq_results WHERE run_id = %s AND dataset_id = %s", (run_id, dataset_id))
        with conn.cursor() as cursor:
            cursor.executemany(
                """
                INSERT INTO ops.dq_results
                    (run_id, dataset_id, rule_id, severity, passed, detail, score_pct, status, scope)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                rows,
            )


def last_success() -> dict[str, tuple[Any, int | None]]:
    with connect() as conn:
        rows = conn.execute(
            """
            SELECT DISTINCT ON (job_id) job_id, ended_at, delta_version FROM ops.runs
            WHERE status = 'success' ORDER BY job_id, ended_at DESC
            """
        ).fetchall()
    return {job_id: (ended_at, version) for job_id, ended_at, version in rows}


SERVING_TABLES = """
    SELECT c.table_schema, c.table_name, c.column_name
    FROM information_schema.columns c
    JOIN information_schema.tables t USING (table_schema, table_name)
    WHERE t.table_type = 'BASE TABLE' AND (c.table_schema LIKE 'mart\\_%' OR c.table_schema IN ('app', 'ops'))
    ORDER BY c.table_schema, c.table_name, c.ordinal_position
"""


def serving_tables(conn) -> dict[str, list[str]]:
    tables: dict[str, list[str]] = {}
    for schema, table, column in conn.execute(SERVING_TABLES).fetchall():
        tables.setdefault(f"{schema}.{table}", []).append(column)
    return tables


def missing_roles(conn, names: list[str]) -> list[str]:
    found = {row[0] for row in conn.execute("SELECT rolname FROM pg_roles WHERE rolname = ANY(%s)", (names,))}
    return [name for name in names if name not in found]


def schema_comments(conn) -> dict[str, str | None]:
    rows = conn.execute("SELECT nspname, obj_description(oid, 'pg_namespace') FROM pg_namespace").fetchall()
    return dict(rows)


def replace_policy_effective(conn, rows: list[tuple[str, str, str, str]]) -> None:
    conn.execute("DELETE FROM ops.policy_effective")
    with conn.cursor() as cursor:
        cursor.executemany(
            'INSERT INTO ops.policy_effective (role, dataset_id, "column", action) VALUES (%s, %s, %s, %s)', rows
        )


def policy_effective(conn, view: bool = False) -> list[tuple[str, str, str, str]]:
    schema = "ops_v" if view else "ops"
    query = f'SELECT role, dataset_id, "column", action FROM {schema}.policy_effective ORDER BY 1, 2, 3'
    return conn.execute(query).fetchall()


def select_privileges(conn, login: str, table: str, view: str, columns: list[str]) -> tuple[bool, list[bool]]:
    base = conn.execute("SELECT has_any_column_privilege(%s, %s, 'SELECT')", (login, table)).fetchone()[0]
    if conn.execute("SELECT to_regclass(%s)", (view,)).fetchone()[0] is None:
        return base, [False] * len(columns)
    granted = conn.execute(
        "SELECT ARRAY(SELECT has_column_privilege(%s, %s, c, 'SELECT') FROM unnest(%s::text[]) AS c)",
        (login, view, columns),
    ).fetchone()[0]
    return base, granted


GATED_RUNS = """
    SELECT r.job_id, coalesce(r.ended_at, r.started_at), r.failing_step,
        ARRAY(SELECT DISTINCT d.dataset_id FROM ops.dq_results d WHERE d.run_id = r.run_id AND d.status = 'Red')
    FROM (
        SELECT DISTINCT ON (job_id) * FROM ops.runs
        WHERE status IN ('success', 'gated') ORDER BY job_id, started_at DESC
    ) r
    WHERE r.status = 'gated'
"""


def gated_runs() -> list[tuple[str, Any, str | None, list[str]]]:
    with connect() as conn:
        return conn.execute(GATED_RUNS).fetchall()


def dq_breaks() -> set[str]:
    with connect() as conn:
        return {row[0] for row in conn.execute("SELECT dataset_id FROM ops.dq_breaks")}


def set_dq_break(dataset_id: str, on: bool) -> None:
    with connect() as conn:
        if on:
            conn.execute("INSERT INTO ops.dq_breaks (dataset_id) VALUES (%s) ON CONFLICT DO NOTHING", (dataset_id,))
        else:
            conn.execute("DELETE FROM ops.dq_breaks WHERE dataset_id = %s", (dataset_id,))
