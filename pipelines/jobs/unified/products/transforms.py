from __future__ import annotations

from typing import TYPE_CHECKING

from pipelines.jobs.unified._common import canonical_expr

if TYPE_CHECKING:
    from pyspark.sql import DataFrame


def build_products(sales: DataFrame, mapping: dict[str, str] | None = None) -> DataFrame:
    """Distinct product dimension from sales lines with canonical category (FR-6, R13)."""
    from pyspark.sql import functions as F

    return (
        sales.groupBy("product_sku").agg(
            F.first("product_description").alias("product_description"),
            F.first("product_category").alias("product_category"),
            F.first("provenance").alias("provenance"),
        )
    ).withColumn("canonical_category", canonical_expr(F.col("product_category"), mapping or {}))
