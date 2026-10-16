from __future__ import annotations

from typing import TYPE_CHECKING

from pipelines.jobs.marts.campaign.campaign_overview.transforms import ALL, ALL_NAME

if TYPE_CHECKING:
    from pyspark.sql import DataFrame

KEYS = ["month", "campaign_id", "product_sku"]


def build(lines: DataFrame, attribution: DataFrame, category_map: DataFrame, campaigns: DataFrame) -> DataFrame:
    from pyspark.sql import functions as F

    spark = lines.sparkSession
    # unmapped categories pass through unchanged (R13), as in unified/_common.canonical_expr
    cats = category_map.select(
        F.col("raw_category").alias("product_category"), F.col("canonical_category").alias("mapped")
    )
    base = (
        lines.drop("canonical_category")
        .join(cats, "product_category", "left")
        .withColumn("canonical_category", F.coalesce("mapped", "product_category"))
        .drop("mapped")
        .withColumn("month", F.trunc("transaction_date_iso", "month"))
    )
    attributed = base.drop("provenance").join(attribution.select("order_key", "campaign_id", "provenance"), "order_key")
    everything = base.withColumn("campaign_id", F.lit(ALL))
    names = campaigns.select("campaign_id", "campaign_name").unionByName(
        spark.createDataFrame([(ALL, ALL_NAME)], "campaign_id string, campaign_name string")
    )
    return (
        attributed.unionByName(everything.select(attributed.columns))
        .groupBy(KEYS)
        .agg(
            F.sum("quantity").alias("quantity"),
            F.sum("line_gross_value").alias("gross_value"),
            # ponytail: one row per grain key; min() picks a deterministic description/category if a SKU has several
            F.min("product_description").alias("product_description"),
            F.min("canonical_category").alias("canonical_category"),
            F.max("provenance").alias("provenance"),  # "synthetic" > "original": any synthetic line taints the row
        )
        .join(names, "campaign_id")
        .select(
            "month",
            "campaign_id",
            "campaign_name",
            "product_sku",
            "product_description",
            "canonical_category",
            F.col("quantity").cast("int").alias("quantity"),
            F.col("gross_value").cast("decimal(18,2)").alias("gross_value"),
            "provenance",
        )
    )
