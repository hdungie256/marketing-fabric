"""Serving Postgres reads and full writes for marts (AD-11, AD-17)."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from pipelines.io.ops import connect
from pipelines.io.scope import Scope, restrict

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


def grain(table: str) -> list[str]:
    from fabric_control.contracts import load_schema

    return load_schema(table)["grain"]


def outside(rows: list[Any], columns: list[str], keys: dict[str, list[Any]]) -> list[Any]:
    index = {c: columns.index(c) for c in keys}
    allowed = {c: {str(v) for v in values} for c, values in keys.items()}
    return [row for row in rows if any(str(row[index[c]]) not in allowed[c] for c in keys)]


def upsert(
    table: str, df: DataFrame, scope: Scope, run_id: str, source_version: dict[str, int]
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    from psycopg import sql
    from psycopg.rows import dict_row

    ident = sql.Identifier(*_table(table, "mart_"))
    scope = restrict(scope, grain(table))
    if scope["mode"] != "scope":
        raise ValueError(f"{table}: scoped write needs keys on grain {grain(table)}")
    collected = df.collect()
    stray = outside(collected, df.columns, scope["keys"])
    if stray:
        raise ValueError(f"{table}: {len(stray)} rows fall outside scope {scope['keys']}")
    where = sql.SQL(" AND ").join(sql.SQL("{}::text = ANY(%s)").format(sql.Identifier(c)) for c in scope["keys"])
    params = [[str(v) for v in values] for values in scope["keys"].values()]
    data = sql.SQL(", ").join(map(sql.Identifier, df.columns))
    order = sql.SQL(", ").join(map(sql.Identifier, grain(table)))
    select = sql.SQL("SELECT {} FROM {} WHERE {} ORDER BY {}").format(data, ident, where, order)
    copy = sql.SQL("COPY {} ({}) FROM STDIN").format(
        ident, sql.SQL(", ").join(map(sql.Identifier, [*df.columns, *META]))
    )
    rows = stamp(collected, run_id, source_version, datetime.now(UTC))
    with connect() as conn, conn.transaction():
        cursor = conn.cursor(row_factory=dict_row)
        before = cursor.execute(select + sql.SQL(" FOR UPDATE"), params).fetchall()
        conn.execute(sql.SQL("DELETE FROM {} WHERE {}").format(ident, where), params)
        with conn.cursor().copy(copy) as out:
            for row in rows:
                out.write_row(row)
        after = cursor.execute(select, params).fetchall()
    return before, after
