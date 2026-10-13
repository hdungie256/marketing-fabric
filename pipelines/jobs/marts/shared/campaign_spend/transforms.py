from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pyspark.sql import DataFrame

MONEY = "decimal(18,2)"


def allocated(spend: DataFrame) -> DataFrame:
    from pyspark.sql import functions as F

    return spend.select(
        "campaign_id", "date", F.col("allocated_online_spend").cast(MONEY).alias("allocated"), "provenance"
    )


def reconciliation(daily: DataFrame, spend: DataFrame) -> DataFrame:
    """Recompute the daily split from unified data, never from the source Spend_Recon (FR-4, R8)."""
    from pyspark.sql import functions as F

    per_day = spend.groupBy("date").agg(
        F.sum("allocated_online_spend").alias("allocated"),
        F.max((F.col("provenance") == "synthetic").cast("int")).alias("synthetic"),
    )
    joined = daily.join(per_day, "date", "left")
    allocated_ = F.coalesce(F.col("allocated"), F.lit(0)).cast(MONEY)
    return joined.select(
        "date",
        F.col("online_spend").cast(MONEY).alias("online_spend"),
        F.col("offline_spend").cast(MONEY).alias("offline_spend"),
        allocated_.alias("allocated"),
        (F.col("online_spend") - allocated_).cast(MONEY).alias("unallocated"),
        F.when(F.col("synthetic") == 1, F.lit("synthetic")).otherwise(F.col("provenance")).alias("provenance"),
    )


def unbalanced_days(recon: DataFrame) -> DataFrame:
    from pyspark.sql import functions as F

    return recon.filter(F.col("allocated") + F.col("unallocated") != F.col("online_spend"))


def total(df: DataFrame, column: str):
    from pyspark.sql import functions as F

    return df.agg(F.sum(column)).first()[0] or 0
