"""Source fault injection for BR15 demos and tests (Story 7.2): `make break-source SRC=<source>` / `make fix-source`.

A fault is a row in meta.source_faults of the sources database. Every ingest checks it before extracting, so the
next load of that source fails with the stored cause, as if the source system were down. Nothing in the app can
set it (no in-app break button).
"""

from __future__ import annotations

import os
import sys

import psycopg

SOURCES = ("sales", "crm", "erp", "campaign", "promotion", "spend", "tax")
DEFAULT_CAUSE = "connection refused (fault injected with make break-source)"
TABLE = """CREATE TABLE IF NOT EXISTS meta.source_faults (
    source text PRIMARY KEY, cause text NOT NULL, set_at timestamptz NOT NULL DEFAULT now())"""


def connect() -> psycopg.Connection:
    return psycopg.connect(os.environ["SOURCES_DB_DSN"], autocommit=True)


def set_fault(source: str, on: bool = True, cause: str = DEFAULT_CAUSE) -> None:
    if source not in SOURCES:
        raise KeyError(f"unknown source {source!r}; one of {', '.join(SOURCES)}")
    with connect() as conn:
        conn.execute(TABLE)
        conn.execute("DELETE FROM meta.source_faults WHERE source = %s", (source,))
        if on:
            conn.execute("INSERT INTO meta.source_faults (source, cause) VALUES (%s, %s)", (source, cause))


def active_fault(source: str) -> str | None:
    """The injected cause for this source, or None. A missing table means no fault was ever set."""
    with connect() as conn:
        if conn.execute("SELECT to_regclass('meta.source_faults')").fetchone()[0] is None:
            return None
        row = conn.execute("SELECT cause FROM meta.source_faults WHERE source = %s", (source,)).fetchone()
    return row[0] if row else None


if __name__ == "__main__":
    action, source = sys.argv[1], sys.argv[2]
    set_fault(source, on=action == "break")
    print(f"{source}: fault {'injected' if action == 'break' else 'cleared'}")
