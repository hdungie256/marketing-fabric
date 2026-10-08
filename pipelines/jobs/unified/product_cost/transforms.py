from __future__ import annotations

from typing import TYPE_CHECKING

from pipelines.jobs.unified._common import canonical_expr

if TYPE_CHECKING:
    from pyspark.sql import DataFrame


def build_product_cost(costs: DataFrame, mapping: dict[str, str] | None = None) -> DataFrame:
    """Cleanse the ERP cost reference and attach the canonical category (FR-6, R11).

    Estimated costs stay estimates: downstream contribution is labelled
    estimated, never net profit (R11).
    """
    from pyspark.sql import functions as F

    return costs.withColumn("canonical_category", canonical_expr(F.col("product_category"), mapping or {})).select(
        "product_sku",
        "product_category",
        "canonical_category",
        "observed_avg_price",
        "estimated_unit_cost",
        "valid_from",
        "valid_through",
        "provenance",
        "provenance_note",
    )
