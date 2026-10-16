from __future__ import annotations

from typing import TYPE_CHECKING

from pipelines.jobs.marts.campaign.campaign_overview.transforms import PERIOD_SCHEMA, _synthetic, periods

if TYPE_CHECKING:
    from pyspark.sql import DataFrame

KEYS = ["period_id", "compare_by", "group_id"]


def _groups(df: DataFrame, campaigns: DataFrame) -> DataFrame:
    """Each row belongs to one campaign group and one channel group."""
    from pyspark.sql import functions as F

    joined = df.join(campaigns.select("campaign_id", "campaign_name", "channel"), "campaign_id")
    by_campaign = joined.select(
        "*",
        F.lit("campaign").alias("compare_by"),
        F.col("campaign_id").alias("group_id"),
        F.col("campaign_name").alias("group_name"),
    )
    by_channel = joined.select(
        "*",
        F.lit("channel").alias("compare_by"),
        F.col("channel").alias("group_id"),
        F.col("channel").alias("group_name"),
    )
    return by_campaign.unionByName(by_channel)


def build(daily: DataFrame, orders: DataFrame, campaigns: DataFrame) -> DataFrame:
    from pyspark.sql import functions as F

    spark = daily.sparkSession
    years = [r[0] for r in daily.select(F.year("date")).distinct().collect()]
    period = spark.createDataFrame(periods(years), PERIOD_SCHEMA)
    in_period = F.col("date").between(F.col("period_start"), F.col("period_end"))
    grid = campaigns.select(
        F.lit("campaign").alias("compare_by"),
        F.col("campaign_id").alias("group_id"),
        F.col("campaign_name").alias("group_name"),
        "channel",
    ).unionByName(
        campaigns.select("channel")
        .distinct()
        .select(
            F.lit("channel").alias("compare_by"),
            F.col("channel").alias("group_id"),
            F.col("channel").alias("group_name"),
            "channel",
        )
    )
    sums = (
        _groups(daily.select("campaign_id", "date", "attributed_orders", "attributed_gross_value"), campaigns)
        .join(period, in_period)
        .groupBy(KEYS)
        .agg(F.sum("attributed_orders").alias("o"), F.sum("attributed_gross_value").alias("v"))
    )
    buyers = (
        _groups(orders.select("campaign_id", "date", "customer_id"), campaigns)
        .join(period, in_period)
        .groupBy(KEYS)
        .agg(F.countDistinct("customer_id").alias("b"))
    )
    provenance = "synthetic" if _synthetic(daily, orders, campaigns) else "original"
    n_orders = F.coalesce(F.col("o"), F.lit(0)).cast("int")
    value = F.coalesce(F.col("v"), F.lit(0)).cast("decimal(18,2)")
    return (
        period.crossJoin(grid)
        .join(sums, KEYS, "left")
        .join(buyers, KEYS, "left")
        .select(
            "period_id",
            "period_label",
            "period_start",
            "period_end",
            "compare_by",
            "group_id",
            "group_name",
            "channel",
            n_orders.alias("attributed_orders"),
            F.coalesce(F.col("b"), F.lit(0)).cast("int").alias("attributed_buyers"),
            value.alias("attributed_gross_value"),
            F.when(n_orders > 0, F.round(value / n_orders, 2)).cast("decimal(18,2)").alias("average_order_value"),
            F.lit(provenance).alias("provenance"),
        )
    )
