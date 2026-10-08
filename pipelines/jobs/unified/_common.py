"""Shared helpers for P3 unified jobs (Story 1.6).

Pure-python mapping loader plus tiny Spark expression builders.
Spark imports stay inside function bodies so this module (and the
mapping loader) remains importable without pyspark, mirroring
`pipelines/io/raw.py` and `pipelines/jobs/ingest/load.py`.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

MAPPING_FILE = Path(__file__).resolve().parents[3] / "governance" / "mappings" / "category.yml"


def load_mapping_rows(path: Path | None = None) -> list[dict[str, str]]:
    """Load category.yml as row dicts matching the unified/ref_category_map schema."""
    doc = yaml.safe_load((path or MAPPING_FILE).read_text()) or {}
    rows = []
    for entry in doc.get("mappings") or []:
        rows.append(
            {
                "raw_category": entry["raw"],
                "canonical_category": entry["canonical"],
                "rule": entry.get("rule", ""),
            }
        )
    return rows


def load_mapping(path: Path | None = None) -> dict[str, str]:
    """Load category.yml as {raw_category: canonical_category} for transforms."""
    return {row["raw_category"]: row["canonical_category"] for row in load_mapping_rows(path)}


def order_key_expr(customer_col: str = "customer_id", transaction_col: str = "transaction_id") -> Any:
    """order_key = customer_id || '|' || transaction_id (R1, FR-5).

    Uses concat (not concat_ws) so a null component yields a null key
    instead of a silently wrong one.
    """
    from pyspark.sql import functions as F

    return F.concat(F.col(customer_col).cast("string"), F.lit("|"), F.col(transaction_col).cast("string"))


def canonical_expr(category_col: Any, mapping: dict[str, str]) -> Any:
    """Map a raw category column to its canonical name (FR-6, R13).

    Unmapped values pass through unchanged, so `Nest`, `Nest-USA` and
    `Nest-Canada` stay three separate categories.
    """
    from pyspark.sql import functions as F

    expr = category_col
    for raw, canonical in mapping.items():
        expr = F.when(category_col == raw, F.lit(canonical)).otherwise(expr)
    return expr


def canonical_column(df: Any, source_col: str = "product_category", target_col: str = "canonical_category") -> Any:
    """Attach the canonical category column to a sales/cost frame (used by jobs)."""
    from pyspark.sql import functions as F

    return df.withColumn(target_col, canonical_expr(F.col(source_col), load_mapping()))
