from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from pyspark.sql import DataFrame

Scope = dict[str, Any]


def read_raw(dataset_id: str) -> DataFrame:
    raise NotImplementedError("read_raw")


def read_delta(dataset_id: str) -> DataFrame:
    raise NotImplementedError("read_delta")


def write_delta(dataset_id: str, df: DataFrame, run_id: str, replace_where: Scope | None = None) -> None:
    raise NotImplementedError("write_delta")


def write_pg_full(table: str, df: DataFrame, run_id: str) -> None:
    raise NotImplementedError("write_pg_full")


def upsert_pg(table: str, df: DataFrame, scope: Scope, run_id: str) -> tuple[Any, Any]:
    raise NotImplementedError("upsert_pg")
