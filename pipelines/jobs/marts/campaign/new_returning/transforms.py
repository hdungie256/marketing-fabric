from __future__ import annotations

from typing import TYPE_CHECKING

from pipelines.jobs.marts.campaign.campaign_overview.transforms import (
    ALL,
    ALL_NAME,
    PERIOD_SCHEMA,
    _synthetic,
    _with_all,
    periods,
)

if TYPE_CHECKING:
    from pyspark.sql import DataFrame

KEYS = ["period_id", "campaign_id"]


def build(orders: DataFrame, campaigns: DataFrame) -> DataFrame:
    from pyspark.sql import functions as F

    spark = orders.sparkSession
    years = [r[0] for r in orders.select(F.year("date")).distinct().collect()]
    period = spark.createDataFrame(periods(years), PERIOD_SCHEMA)
    names = campaigns.select("campaign_id", "campaign_name").unionByName(
        spark.createDataFrame([(ALL, ALL_NAME)], "campaign_id string, campaign_name string")
    )
    in_period = F.col("date").between(F.col("period_start"), F.col("period_end"))
    buyers = (
        _with_all(orders.select("campaign_id", "date", "customer_id", "is_first_observed"))
        .join(period, in_period)
        .groupBy(KEYS)
        .agg(
            F.countDistinct("customer_id").alias("b"),
            F.countDistinct(F.when(F.col("is_first_observed"), F.col("customer_id"))).alias("f"),
        )
    )
    provenance = "synthetic" if _synthetic(orders, campaigns) else "original"
    total = F.coalesce(F.col("b"), F.lit(0)).cast("int")
    first = F.coalesce(F.col("f"), F.lit(0)).cast("int")
    return (
        period.crossJoin(names)
        .join(buyers, KEYS, "left")
        .select(
            "period_id",
            "period_label",
            "period_start",
            "period_end",
            "campaign_id",
            "campaign_name",
            total.alias("attributed_buyers"),
            first.alias("first_observed_buyers"),
            (total - first).alias("returning_buyers"),
            F.lit(provenance).alias("provenance"),
        )
    )
