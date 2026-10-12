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
