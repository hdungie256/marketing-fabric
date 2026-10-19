from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pyspark.sql import DataFrame


def merge(*frames: DataFrame) -> DataFrame:
    """Union every exception class into the shared list (FR-8).

    All producers select the contracts/exceptions.yml columns in the same
    order, so unionByName is exact. Lake metadata (_run_id) is dropped: the
    PG writer stamps its own _refreshed_at/_run_id/_source_version. Provenance is original: every class
    derives from original sales/coupon sources. The UI reads only this mart.
    """
    from pyspark.sql import functions as F

    merged = frames[0]
    for frame in frames[1:]:
        merged = merged.unionByName(frame)
    merged = merged.drop(*[c for c in merged.columns if c.startswith("_")])
    return merged.withColumn("provenance", F.lit("original"))
