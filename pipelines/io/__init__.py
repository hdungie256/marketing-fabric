from __future__ import annotations

import os
from typing import TYPE_CHECKING, Any

from pipelines.io import lineage, ops, pg, raw
from pipelines.io.scope import Scope, narrow, restrict, scope_predicate
from pipelines.io.spark import get_spark
from pipelines.io.storage import table_path

if TYPE_CHECKING:
    from pyspark.sql import DataFrame

__all__ = [
    "Scope",
    "append_raw",
    "delta_version",
    "get_spark",
    "narrow",
    "read_delta",
    "read_pg",
    "read_raw",
    "restrict",
    "source_versions",
    "upsert_pg",
    "vacuum",
    "write_delta",
    "write_pg_full",
]


def read_raw(dataset_id: str) -> DataFrame:
    from pyspark.sql import functions as F

    from fabric_control.registry import load_registry

    entry = load_registry()[dataset_id]
    if entry.get("derived"):
        raise ValueError(f"{dataset_id} is derived at the source and must not be read as a fact")
    keys = entry["natural_key"]
    loads = read_delta(dataset_id).filter(F.col("_load_id").isin(ops.passed_loads(dataset_id)))
    return raw.latest_per_key(loads, keys)


def source_versions(dataset_ids: list[str]) -> dict[str, int]:
    from pyspark.sql import functions as F

    from pipelines.dags.job_graph import writers

    versions = {}
    for raw_id in lineage.raw_ancestors(dataset_ids, writers(lineage.ROOT), lineage.job_inputs):
        version = read_raw(raw_id).agg(F.max("_source_version")).first()[0]
        if version is None:
            raise ValueError(f"{raw_id} has no passed load")
        versions[raw_id] = int(version)
    return versions


def append_raw(
    dataset_id: str,
    df: DataFrame,
    run_id: str,
    source: str,
    load_kind: str,
    source_version: int,
    schema_version: str,
    load_id: str | None = None,
) -> str:
    if not dataset_id.startswith("raw/"):
        raise ValueError(f"{dataset_id} is not a raw dataset")
    load_id = load_id or raw.new_load_id()
    write_delta(dataset_id, raw.stamp(df, load_id, source, load_kind, source_version, schema_version), run_id)
    return load_id


def delta_version(dataset_id: str) -> int:
    from delta.tables import DeltaTable

    return DeltaTable.forPath(get_spark(), table_path(dataset_id)).history(1).collect()[0].version


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


def read_pg(table: str) -> DataFrame:
    """Read a serving table (e.g. a mart_shared input of a slice mart) over JDBC as the job login."""
    from psycopg.conninfo import conninfo_to_dict

    dsn = conninfo_to_dict(os.environ["SERVING_DB_DSN"])
    return (
        get_spark()
        .read.format("jdbc")
        .option("url", f"jdbc:postgresql://{dsn['host']}:{dsn.get('port', 5432)}/{dsn['dbname']}")
        .option("dbtable", table)
        .option("user", dsn["user"])
        .option("password", dsn["password"])
        .option("driver", "org.postgresql.Driver")
        .load()
    )


def write_pg_full(table: str, df: DataFrame, run_id: str, source_version: dict[str, int]) -> None:
    pg.write_full(table, df, run_id, source_version)


def upsert_pg(
    table: str, df: DataFrame, scope: Scope, run_id: str, source_version: dict[str, int]
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    return pg.upsert(table, df, scope, run_id, source_version)
