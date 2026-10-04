from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pyspark.sql import DataFrame

LOAD_COLUMNS = ("_load_id", "_ingested_at", "_source", "_load_kind", "_source_version", "_schema_version")


def stamp(
    df: DataFrame, load_id: str, source: str, load_kind: str, source_version: int, schema_version: str
) -> DataFrame:
    from pyspark.sql import functions as F

    return (
        df.withColumn("_load_id", F.lit(load_id))
        .withColumn("_ingested_at", F.current_timestamp())
        .withColumn("_source", F.lit(source))
        .withColumn("_load_kind", F.lit(load_kind))
        .withColumn("_source_version", F.lit(source_version).cast("bigint"))
        .withColumn("_schema_version", F.lit(schema_version))
    )


def new_load_id() -> str:
    return uuid.uuid4().hex


def latest_per_key(df: DataFrame, keys: list[str]) -> DataFrame:
    from pyspark.sql import Window
    from pyspark.sql import functions as F

    window = Window.partitionBy(*keys).orderBy(F.col("_source_version").desc(), F.col("_ingested_at").desc())
    return df.withColumn("_rank", F.row_number().over(window)).filter(F.col("_rank") == 1).drop("_rank")
