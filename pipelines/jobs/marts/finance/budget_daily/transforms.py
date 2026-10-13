from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pyspark.sql import DataFrame

MONEY = "decimal(18,2)"
KEYS = ["campaign_id", "date"]


def budget_daily(spend: DataFrame, attributed: DataFrame, campaigns: DataFrame) -> DataFrame:
    """One row per campaign-day with spend or attributed orders; campaign_budget repeats per row (never sum it)."""
    from pyspark.sql import functions as F

    spend = spend.select(*KEYS, "allocated", F.col("provenance").alias("spend_provenance"))
    attributed = attributed.select(
        *KEYS, "attributed_orders", "attributed_gross_value", F.col("provenance").alias("order_provenance")
    )
    synthetic = (F.col("spend_provenance") == "synthetic") | (F.col("order_provenance") == "synthetic")
    days = spend.join(attributed, KEYS, "full").join(
        campaigns.select("campaign_id", "campaign_name", "channel", F.col("budget").alias("campaign_budget")),
        "campaign_id",
        "left",
    )
    return days.select(
        *KEYS,
        "campaign_name",
        "channel",
        F.col("campaign_budget").cast(MONEY).alias("campaign_budget"),
        F.coalesce("allocated", F.lit(0)).cast(MONEY).alias("allocated"),
        F.coalesce("attributed_orders", F.lit(0)).cast("int").alias("attributed_orders"),
        F.coalesce("attributed_gross_value", F.lit(0)).cast(MONEY).alias("attributed_gross_value"),
        F.when(synthetic, F.lit("synthetic"))
        .otherwise(F.coalesce("spend_provenance", "order_provenance"))
        .alias("provenance"),
    )


def in_scope(df: DataFrame, scope: dict) -> DataFrame:
    """Keep rows matching the scope keys this frame has; keys it lacks do not narrow it (AD-6)."""
    from pyspark.sql import functions as F

    if scope.get("mode") != "scope":
        return df
    for column, values in scope["keys"].items():
        if column in df.columns:
            df = df.filter(F.col(column).isin(values))
    return df


def total(df: DataFrame, column: str):
    from pyspark.sql import functions as F

    return df.agg(F.sum(column)).first()[0] or 0
