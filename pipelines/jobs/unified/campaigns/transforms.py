from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pyspark.sql import DataFrame

MAP_SOURCE = "raw_category"
MAP_TARGET = "canonical_category"
COLUMNS = [
    "campaign_id",
    "campaign_name",
    "channel",
    "start_date",
    "end_date",
    "target_category",
    "source_target_category",
    "objective",
    "budget",
    "provenance",
    "provenance_note",
]


def normalize_category(
    df: DataFrame, column: str, category_map: DataFrame, source_column: str | None = None
) -> DataFrame:
    from pyspark.sql import functions as F

    source_column = source_column or f"source_{column}"
    mapping = category_map.select(
        F.col(MAP_SOURCE).alias("_map_source"), F.col(MAP_TARGET).alias("_map_target")
    ).dropDuplicates(["_map_source"])
    return (
        df.withColumnRenamed(column, source_column)
        .join(F.broadcast(mapping), F.col(source_column) == F.col("_map_source"), "left")
        .withColumn(column, F.coalesce(F.col("_map_target"), F.col(source_column)))
        .drop("_map_source", "_map_target")
    )


def unknown_campaigns(df: DataFrame, campaigns: DataFrame) -> DataFrame:
    return df.join(campaigns.select("campaign_id"), "campaign_id", "left_anti")


def transform(raw: DataFrame, category_map: DataFrame) -> DataFrame:
    return normalize_category(raw, "target_category", category_map).select(*COLUMNS)
