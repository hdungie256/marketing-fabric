from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pyspark.sql import DataFrame


def transform(df: DataFrame) -> DataFrame:
    return df
