"""Serving Postgres reads and full writes for marts (AD-11, AD-17)."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from pipelines.io.ops import connect

if TYPE_CHECKING:
    from pyspark.sql import DataFrame

META = ("_refreshed_at", "_run_id", "_source_version")


def _table(name: str, prefix: str) -> tuple[str, str]:
    from fabric_control.registry import load_registry

    schema, _, table = name.partition(".")
    if not schema.startswith(prefix) or not table or name not in load_registry():
        raise ValueError(f"{name}: expected a registered {prefix}* table")
    return schema, table


def stamp(rows: list[Any], run_id: str, source_version: dict[str, int], now: datetime) -> list[tuple]:
    version = json.dumps(source_version, sort_keys=True)
    return [(*row, now, run_id, version) for row in rows]


def write_full(table: str, df: DataFrame, run_id: str, source_version: dict[str, int]) -> None:
    from psycopg import sql

    ident = sql.Identifier(*_table(table, "mart_"))
    columns = [*df.columns, *META]
    # ponytail: rows go through the driver; fine for mart-sized tables, switch to JDBC if a mart grows past ~1M rows
    rows = stamp(df.collect(), run_id, source_version, datetime.now(UTC))
    copy = sql.SQL("COPY {} ({}) FROM STDIN").format(ident, sql.SQL(", ").join(map(sql.Identifier, columns)))
    with connect() as conn, conn.transaction():
        conn.execute(sql.SQL("TRUNCATE {}").format(ident))
        with conn.cursor().copy(copy) as out:
            for row in rows:
                out.write_row(row)
