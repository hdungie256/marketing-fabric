from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pyspark.sql import DataFrame

MONEY = "decimal(18,2)"


def _synthetic(*columns: str):
    from pyspark.sql import functions as F

    return F.when(F.greatest(*[(F.col(c) == "synthetic").cast("int") for c in columns]) == 1, "synthetic").otherwise(
        "original"
    )


def contribution_sku(lines: DataFrame, attribution: DataFrame, product_cost: DataFrame) -> DataFrame:
    """Attributed lines per campaign and SKU with reference cost of goods; a line sold outside the cost's validity
    window, or a SKU with no reference cost, has no cost and makes the SKU an item not yet available (FR-35)."""
    from pyspark.sql import functions as F

    attributed = lines.select(
        "order_key",
        "product_sku",
        "product_description",
        "quantity",
        "line_gross_value",
        "transaction_date_iso",
        F.col("provenance").alias("line_provenance"),
    ).join(attribution.select("order_key", "campaign_id", F.col("provenance").alias("link_provenance")), "order_key")
    cost = product_cost.select(
        F.col("product_sku").alias("cost_sku"),
        "estimated_unit_cost",
        "valid_from",
        "valid_through",
        F.col("provenance").alias("cost_provenance"),
    )
    valid = (F.col("product_sku") == F.col("cost_sku")) & F.col("transaction_date_iso").between(
        F.col("valid_from"), F.col("valid_through")
    )
    joined = attributed.join(cost, valid, "left")
    grouped = joined.groupBy("campaign_id", "product_sku").agg(
        F.first("product_description").alias("product_description"),
        F.sum("quantity").cast("bigint").alias("quantity"),
        F.sum("line_gross_value").cast(MONEY).alias("attributed_gross_value"),
        F.max("estimated_unit_cost").cast(MONEY).alias("estimated_unit_cost"),
        F.sum(F.col("quantity") * F.col("estimated_unit_cost")).cast(MONEY).alias("cogs"),
        (F.count("estimated_unit_cost") == F.count("*")).alias("cost_available"),
        F.max(_synthetic("line_provenance", "link_provenance", "cost_provenance")).alias("provenance"),
    )
    return grouped.select(
        "campaign_id",
        "product_sku",
        "product_description",
        "quantity",
        "attributed_gross_value",
        "estimated_unit_cost",
        F.when(F.col("cost_available"), F.col("cogs")).alias("reference_cogs"),
        "cost_available",
        "provenance",
    )


def contribution(skus: DataFrame, campaigns: DataFrame, spend: DataFrame, attributed_daily: DataFrame) -> DataFrame:
    """Estimated Contribution = attributed gross value − reference cost of goods − campaign cost (FR-35, R11).

    Attributed gross value comes from mart_shared (AD-11); SKUs without reference cost add no cost of goods and are
    counted in skus_without_cost so the page can label the estimate."""
    from pyspark.sql import functions as F

    cogs = skus.groupBy("campaign_id").agg(
        F.sum("reference_cogs").alias("reference_cogs"),
        F.sum((~F.col("cost_available")).cast("int")).alias("skus_without_cost"),
        F.max("provenance").alias("sku_provenance"),
    )
    cost = spend.groupBy("campaign_id").agg(
        F.sum("allocated").alias("campaign_cost"), F.max("provenance").alias("spend_provenance")
    )
    gross = attributed_daily.groupBy("campaign_id").agg(
        F.sum("attributed_gross_value").alias("attributed_gross_value"), F.max("provenance").alias("order_provenance")
    )
    zero = F.lit(0).cast(MONEY)
    out = (
        campaigns.select("campaign_id", "campaign_name", "provenance")
        .join(gross, "campaign_id", "left")
        .join(cogs, "campaign_id", "left")
        .join(cost, "campaign_id", "left")
        .select(
            "campaign_id",
            "campaign_name",
            F.coalesce("attributed_gross_value", zero).cast(MONEY).alias("attributed_gross_value"),
            F.coalesce("reference_cogs", zero).cast(MONEY).alias("reference_cogs"),
            F.coalesce("campaign_cost", zero).cast(MONEY).alias("campaign_cost"),
            F.coalesce("skus_without_cost", F.lit(0)).cast("int").alias("skus_without_cost"),
            F.coalesce(
                _synthetic("provenance", "order_provenance", "sku_provenance", "spend_provenance"), F.lit("original")
            ).alias("provenance"),
        )
    )
    estimate = F.col("attributed_gross_value") - F.col("reference_cogs") - F.col("campaign_cost")
    return out.select(
        "campaign_id",
        "campaign_name",
        "attributed_gross_value",
        "reference_cogs",
        "campaign_cost",
        estimate.cast(MONEY).alias("estimated_contribution"),
        "skus_without_cost",
        "provenance",
    )


def gross_mismatch(skus: DataFrame, attributed_daily: DataFrame) -> DataFrame:
    """Campaigns whose SKU detail does not add up to the shared attributed gross value."""
    from pyspark.sql import functions as F

    detail = skus.groupBy("campaign_id").agg(F.sum("attributed_gross_value").alias("detail"))
    shared = attributed_daily.groupBy("campaign_id").agg(F.sum("attributed_gross_value").alias("shared"))
    return detail.join(shared, "campaign_id", "full").filter(
        F.coalesce("detail", F.lit(0)) != F.coalesce("shared", F.lit(0))
    )
