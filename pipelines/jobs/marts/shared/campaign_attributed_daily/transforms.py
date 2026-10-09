from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pyspark.sql import DataFrame


def attributed_orders(attribution: DataFrame, orders: DataFrame, customers: DataFrame) -> DataFrame:
    from pyspark.sql import functions as F

    first_day = F.col("order_date") == F.col("first_observed_order_date")
    return (
        attribution.select("order_key", "customer_id", "campaign_id", "order_date", "provenance")
        .join(orders.select("order_key", "gross_value"), "order_key")
        .join(customers.select("customer_id", "first_observed_order_date"), "customer_id")
        .select(
            "order_key",
            "campaign_id",
            F.col("order_date").alias("date"),
            "customer_id",
            F.col("gross_value").cast("decimal(18,2)").alias("gross_value"),
            F.coalesce(first_day, F.lit(False)).alias("is_first_observed"),
            "provenance",
        )
    )


def daily(per_order: DataFrame) -> DataFrame:
    from pyspark.sql import functions as F

    synthetic = F.max((F.col("provenance") == "synthetic").cast("int")) == 1
    return per_order.groupBy("campaign_id", "date").agg(
        F.count("order_key").cast("int").alias("attributed_orders"),
        F.sum("gross_value").cast("decimal(18,2)").alias("attributed_gross_value"),
        F.countDistinct("customer_id").cast("int").alias("buyers"),
        F.countDistinct(F.when(F.col("is_first_observed"), F.col("customer_id")))
        .cast("int")
        .alias("first_observed_buyers"),
        F.when(synthetic, F.lit("synthetic")).otherwise(F.max("provenance")).alias("provenance"),
    )


def missing_orders(attribution: DataFrame, orders: DataFrame) -> DataFrame:
    return attribution.join(orders.select("order_key"), "order_key", "left_anti")


def missing_customers(attribution: DataFrame, customers: DataFrame) -> DataFrame:
    return attribution.join(customers.select("customer_id"), "customer_id", "left_anti")
