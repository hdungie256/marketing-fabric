from __future__ import annotations

from typing import TYPE_CHECKING, Any

from pipelines.io.scope import Scope, scope_predicate
from pipelines.io.spark import get_spark
from pipelines.io.storage import table_path

if TYPE_CHECKING:
    from pyspark.sql import DataFrame

__all__ = ["Scope", "get_spark", "read_delta", "read_raw", "upsert_pg", "vacuum", "write_delta", "write_pg_full"]


def read_raw(dataset_id: str) -> DataFrame:
    raise NotImplementedError("read_raw")


def read_delta(dataset_id: str, version: int | None = None) -> DataFrame:
    reader = get_spark().read.format("delta")
    if version is not None:
        reader = reader.option("versionAsOf", version)
    return reader.load(table_path(dataset_id))


def write_delta(dataset_id: str, df: DataFrame, run_id: str, replace_where: Scope | None = None) -> None:
    from pyspark.sql import functions as F

    writer = df.withColumn("_run_id", F.lit(run_id)).write.format("delta")
    if dataset_id.startswith("raw/"):
        if replace_where:
            raise ValueError("raw datasets are append-only")
        writer.mode("append").save(table_path(dataset_id))
        return
    predicate = scope_predicate(replace_where)
    if predicate:
        writer = writer.option("replaceWhere", predicate)
    writer.mode("overwrite").save(table_path(dataset_id))


def vacuum(dataset_id: str, retention_hours: int = 168) -> None:
    from delta.tables import DeltaTable

    DeltaTable.forPath(get_spark(), table_path(dataset_id)).vacuum(retention_hours)


def write_pg_full(table: str, df: DataFrame, run_id: str) -> None:
    raise NotImplementedError("write_pg_full")


def upsert_pg(table: str, df: DataFrame, scope: Scope, run_id: str) -> tuple[Any, Any]:
    raise NotImplementedError("upsert_pg")
