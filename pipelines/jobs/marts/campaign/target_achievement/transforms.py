from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pyspark.sql import DataFrame

METRIC_COLUMN = {
    "Gross item value": "attributed_gross_value",
    "Attributed order count": "attributed_orders",
    "First observed buyer count": "first_observed_buyers",
}
CONTINUE_AT = 1.0
STOP_BELOW = 0.7
MONEY = "decimal(18,2)"


def narrow(df: DataFrame, scope: dict) -> DataFrame:
    """Scope events carry {campaign_id, date}; only campaign_id narrows, so a campaign is always recomputed over its full window."""
    ids = scope.get("keys", {}).get("campaign_id")
    if scope.get("mode") != "scope" or ids is None:
        return df
    return df.filter(df["campaign_id"].isin(list(ids)))


def build(targets: DataFrame, campaigns: DataFrame, daily: DataFrame, spend: DataFrame) -> DataFrame:
    from pyspark.sql import functions as F

    unknown = sorted(
        {r[0] for r in targets.select("target_metric").distinct().collect()} - set(METRIC_COLUMN)
    )
    if unknown:
        raise ValueError(f"unknown target_metric {unknown}; expected one of {sorted(METRIC_COLUMN)}")
    window = ["campaign_id"]
    in_window = (F.col("date") >= F.col("evaluation_from")) & (F.col("date") <= F.col("evaluation_through"))
    t = targets.select(
        "campaign_id",
        F.create_map(*[x for k, v in METRIC_COLUMN.items() for x in (F.lit(k), F.lit(v))])[F.col("target_metric")].alias(
            "target_metric"
        ),
        "target_value",
        "evaluation_from",
        "evaluation_through",
    )
    sales = (
        t.join(daily, window)
        .filter(in_window)
        .groupBy(window)
        .agg(
            F.sum("attributed_gross_value").alias("attributed_gross_value"),
            F.sum("attributed_orders").alias("attributed_orders"),
            F.sum("first_observed_buyers").alias("first_observed_buyers"),
        )
    )
    cost = t.join(spend, window).filter(in_window).groupBy(window).agg(F.sum("allocated").alias("allocated_spend"))
    df = t.join(campaigns.select("campaign_id", "campaign_name"), window).join(sales, window, "left").join(cost, window, "left")
    actual = F.coalesce(
        F.when(F.col("target_metric") == "attributed_gross_value", F.col("attributed_gross_value"))
        .when(F.col("target_metric") == "attributed_orders", F.col("attributed_orders"))
        .otherwise(F.col("first_observed_buyers")),
        F.lit(0),
    ).cast(MONEY)
    ratio = actual.cast("double") / F.col("target_value").cast("double")
    return df.select(
        "campaign_id",
        "campaign_name",
        "target_metric",
        "target_value",
        "evaluation_from",
        "evaluation_through",
        actual.alias("actual"),
        ratio.cast("decimal(9,6)").alias("achievement"),
        F.coalesce("allocated_spend", F.lit(0)).cast(MONEY).alias("allocated_spend"),
        F.when(ratio >= CONTINUE_AT, "continue").when(ratio >= STOP_BELOW, "adjust").otherwise("stop").alias("recommendation"),
        F.lit("synthetic").alias("provenance"),
    )
