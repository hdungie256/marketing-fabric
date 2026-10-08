from __future__ import annotations

from typing import TYPE_CHECKING

from pipelines.jobs.unified._common import order_key_expr

if TYPE_CHECKING:
    from pyspark.sql import DataFrame


def build_orders(sales: DataFrame) -> DataFrame:
    """Aggregate sales lines to one row per order (FR-5, R1-R3).

    gross_value = SUM(quantity x avg_price); shipping_fee is counted once
    per order via max() because the source repeats the charge on every
    line (R17 storage convention).
    """
    from pyspark.sql import functions as F

    lines = sales.withColumn("order_key", order_key_expr()).withColumn(
        "line_gross", F.col("quantity") * F.col("avg_price")
    )
    return (
        lines.groupBy("order_key", "customer_id", "transaction_id")
        .agg(
            F.first("canonical_order_id").alias("canonical_order_id"),
            F.min("transaction_date_iso").alias("order_date"),
            F.sum("line_gross").alias("gross_value"),
            F.max("delivery_charges").alias("shipping_fee"),
            F.count("*").cast("int").alias("line_count"),
            F.first("provenance").alias("provenance"),
        )
        .select(
            "order_key",
            "customer_id",
            "transaction_id",
            "canonical_order_id",
            "order_date",
            "gross_value",
            "shipping_fee",
            "line_count",
            "provenance",
        )
    )
