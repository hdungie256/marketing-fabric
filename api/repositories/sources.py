import os
from typing import Any

import psycopg
from psycopg import sql
from psycopg.rows import dict_row


def connect():
    return psycopg.connect(os.environ["SOURCES_DB_DSN"], row_factory=dict_row)


def fetch_table(source: str, table: str) -> list[dict[str, Any]]:
    query = sql.SQL("SELECT * FROM {}.{} ORDER BY 1").format(sql.Identifier(source), sql.Identifier(table))
    with connect() as conn:
        return conn.execute(query).fetchall()


def source_version(source: str) -> int:
    with connect() as conn:
        row = conn.execute("SELECT version FROM meta.source_versions WHERE source = %s", (source,)).fetchone()
    return row["version"] if row else 0
