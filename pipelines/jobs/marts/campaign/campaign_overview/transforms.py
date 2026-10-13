from __future__ import annotations

from collections.abc import Iterable
from datetime import date, timedelta
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pyspark.sql import DataFrame

ALL = "ALL"
ALL_NAME = "All campaigns"
KEYS = ["period_id", "campaign_id"]
PERIOD_SCHEMA = "period_id string, period_label string, period_start date, period_end date"


def periods(years: Iterable[int]) -> list[tuple[str, str, date, date]]:
    out = []
    for y in sorted(set(years)):
        out.append((f"FY{y}", f"Jan–Dec {y}", date(y, 1, 1), date(y, 12, 31)))
        for q in range(1, 5):
            end = date(y, 12, 31) if q == 4 else date(y, 3 * q + 1, 1) - timedelta(days=1)
            out.append((f"{y}-Q{q}", f"Q{q} {y}", date(y, 3 * q - 2, 1), end))
    return out


def _with_all(df: DataFrame) -> DataFrame:
    from pyspark.sql import functions as F

    return df.unionByName(df.withColumn("campaign_id", F.lit(ALL)))


def _synthetic(*frames: DataFrame) -> bool:
    from pyspark.sql import functions as F

    return any(not df.filter(F.col("provenance") == "synthetic").isEmpty() for df in frames)


def build(daily: DataFrame, orders: DataFrame, campaigns: DataFrame) -> DataFrame:
    from pyspark.sql import functions as F

    spark = daily.sparkSession
    years = [r[0] for r in daily.select(F.year("date")).distinct().collect()]
    period = spark.createDataFrame(periods(years), PERIOD_SCHEMA)
    names = campaigns.select("campaign_id", "campaign_name").unionByName(
        spark.createDataFrame([(ALL, ALL_NAME)], "campaign_id string, campaign_name string")
    )
    in_period = F.col("date").between(F.col("period_start"), F.col("period_end"))
    sums = (
        _with_all(daily.select("campaign_id", "date", "attributed_orders", "attributed_gross_value"))
        .join(period, in_period)
        .groupBy(KEYS)
        .agg(F.sum("attributed_orders").alias("o"), F.sum("attributed_gross_value").alias("v"))
    )
    buyers = (
        _with_all(orders.select("campaign_id", "date", "customer_id"))
        .join(period, in_period)
        .groupBy(KEYS)
        .agg(F.countDistinct("customer_id").alias("b"))
    )
    provenance = "synthetic" if _synthetic(daily, orders, campaigns) else "original"
    n_orders = F.coalesce(F.col("o"), F.lit(0)).cast("int")
    value = F.coalesce(F.col("v"), F.lit(0)).cast("decimal(18,2)")
    return (
        period.crossJoin(names)
        .join(sums, KEYS, "left")
        .join(buyers, KEYS, "left")
        .select(
            "period_id",
            "period_label",
            "period_start",
            "period_end",
            "campaign_id",
            "campaign_name",
            n_orders.alias("attributed_orders"),
            F.coalesce(F.col("b"), F.lit(0)).cast("int").alias("attributed_buyers"),
            value.alias("attributed_gross_value"),
            F.when(n_orders > 0, F.round(value / n_orders, 2)).cast("decimal(18,2)").alias("average_order_value"),
            F.lit(provenance).alias("provenance"),
        )
    )
