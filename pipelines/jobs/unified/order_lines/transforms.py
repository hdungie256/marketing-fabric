from __future__ import annotations

from typing import TYPE_CHECKING

from pipelines.jobs.unified._common import canonical_expr, order_key_expr

if TYPE_CHECKING:
    from pyspark.sql import DataFrame


def build_order_lines(sales: DataFrame, mapping: dict[str, str] | None = None) -> DataFrame:
    """Cleanse sales lines: stable order key, line gross and canonical category (FR-6, R13)."""
    from pyspark.sql import functions as F

    return (
        sales.withColumn("order_key", order_key_expr())
        .withColumn("line_gross_value", F.col("quantity") * F.col("avg_price"))
        .withColumn("canonical_category", canonical_expr(F.col("product_category"), mapping or {}))
        .select(
            "sales_line_id",
            "order_key",
            "customer_id",
            "transaction_id",
            "transaction_date_iso",
            "product_sku",
            "product_description",
            "product_category",
            "canonical_category",
            "quantity",
            "avg_price",
            "line_gross_value",
            "delivery_charges",
            "coupon_status",
            "provenance",
        )
    )
