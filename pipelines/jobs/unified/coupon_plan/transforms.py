from __future__ import annotations

from typing import TYPE_CHECKING

from pipelines.jobs.unified.campaigns.transforms import normalize_category

if TYPE_CHECKING:
    from datetime import datetime

    from pyspark.sql import DataFrame

EXCEPTION_CLASS = "coupon_plan_duplicate"
DATASET_ID = "unified/coupon_plan"
MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
COLUMNS = ["month", "product_category", "source_category", "coupon_code", "discount_pct", "provenance"]


def month_number(df: DataFrame) -> DataFrame:
    from pyspark.sql import functions as F

    numbers = F.create_map(*[F.lit(v) for i, name in enumerate(MONTHS, 1) for v in (name, i)])
    return df.withColumn("month", numbers[F.initcap(F.trim(F.col("month")))].cast("int"))


def transform(raw: DataFrame, category_map: DataFrame) -> tuple[DataFrame, DataFrame]:
    from pyspark.sql import Window
    from pyspark.sql import functions as F

    df = normalize_category(month_number(raw), "product_category", category_map, source_column="source_category")
    renamed = (F.col("source_category") != F.col("product_category")).cast("int")
    window = Window.partitionBy("month", "product_category").orderBy(renamed, F.col("coupon_code"))
    ranked = df.withColumn("_rank", F.row_number().over(window))
    kept = ranked.filter(F.col("_rank") == 1).select(*COLUMNS)
    dropped = ranked.filter(F.col("_rank") > 1).select(*COLUMNS)
    return kept, dropped


def exceptions(dropped: DataFrame, kept: DataFrame, detected_at: datetime) -> DataFrame:
    from pyspark.sql import functions as F

    winners = kept.select(
        F.col("month").alias("_w_month"),
        F.col("product_category").alias("_w_category"),
        F.col("coupon_code").alias("_kept_code"),
    )
    natural_key = F.concat_ws(
        "|", F.coalesce(F.col("month").cast("string"), F.lit("?")), F.col("product_category"), F.col("coupon_code")
    )
    return dropped.join(
        winners,
        F.col("month").eqNullSafe(F.col("_w_month")) & (F.col("product_category") == F.col("_w_category")),
    ).select(
        F.sha1(F.concat_ws("|", F.lit(EXCEPTION_CLASS), natural_key)).alias("exception_id"),
        F.lit(EXCEPTION_CLASS).alias("class"),
        natural_key.alias("natural_key"),
        F.lit(DATASET_ID).alias("dataset_id"),
        F.format_string("source_category=%s; kept coupon_code=%s", F.col("source_category"), F.col("_kept_code")).alias(
            "detail"
        ),
        F.lit(detected_at).cast("timestamp").alias("detected_at"),
    )
