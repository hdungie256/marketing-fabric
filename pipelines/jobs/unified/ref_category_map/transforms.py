from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from pyspark.sql import DataFrame


def build_map(spark: Any, rows: list[dict[str, str]]) -> DataFrame:
    """Materialize the category mapping file as the ref_category_map dataset (FR-6)."""
    return spark.createDataFrame(rows, "raw_category STRING, canonical_category STRING, rule STRING")
