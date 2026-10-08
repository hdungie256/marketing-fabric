from __future__ import annotations

from typing import TYPE_CHECKING

from pipelines.jobs.unified.campaigns.transforms import normalize_category

if TYPE_CHECKING:
    from pyspark.sql import DataFrame

COLUMNS = [
    "order_key",
    "customer_id",
    "transaction_id",
    "canonical_order_id",
    "order_date",
    "campaign_id",
    "matched_category",
    "source_matched_category",
    "attribution_rule",
    "provenance",
    "provenance_note",
]


def with_order_key(df: DataFrame) -> DataFrame:
    from pyspark.sql import functions as F

    key = F.concat_ws("|", F.col("customer_id").cast("string"), F.col("transaction_id").cast("string"))
    return df.withColumn("order_key", key)


def transform(raw: DataFrame, category_map: DataFrame) -> DataFrame:
    df = with_order_key(raw).withColumnRenamed("transaction_date_iso", "order_date")
    return normalize_category(df, "matched_category", category_map).select(*COLUMNS)


def orphan_links(attribution: DataFrame, orders: DataFrame) -> DataFrame:
    return attribution.join(orders.select("order_key"), "order_key", "left_anti")


def outside_campaign_window(attribution: DataFrame, campaigns: DataFrame) -> DataFrame:
    from pyspark.sql import functions as F

    window = campaigns.select("campaign_id", "start_date", "end_date")
    outside = (F.col("order_date") < F.col("start_date")) | (F.col("order_date") > F.col("end_date"))
    return attribution.join(window, "campaign_id").filter(outside).select(*attribution.columns)
