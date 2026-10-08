from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pyspark.sql import DataFrame

COLUMNS = [
    "campaign_id",
    "target_metric",
    "target_value",
    "evaluation_from",
    "evaluation_through",
    "target_note",
    "provenance",
    "provenance_note",
]


def transform(raw: DataFrame) -> DataFrame:
    return raw.select(*COLUMNS)
