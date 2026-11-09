from __future__ import annotations

from typing import TYPE_CHECKING

from pipelines.jobs.unified._common import canonical_expr

if TYPE_CHECKING:
    from datetime import datetime

    from pyspark.sql import DataFrame

SHARED_CLASS = "shared_transaction_id"
MISMATCH_CLASS = "coupon_plan_mismatch"
SHARED_DATASET = "unified/orders"
MISMATCH_DATASET = "unified/order_lines"
EXCEPTION_COLUMNS = ["exception_id", "class", "natural_key", "dataset_id", "detail", "detected_at"]


def exception_id(class_name: str, natural_key: str) -> str:
    import hashlib

    return hashlib.sha1(f"{class_name}|{natural_key}".encode()).hexdigest()


def shared_transaction_ids(sales: DataFrame, detected_at: datetime) -> DataFrame:
    """Transaction codes seen under more than one customer (R1, FR-8, AC02)."""
    from pyspark.sql import functions as F

    dupes = (
        sales.groupBy("transaction_id")
        .agg(F.countDistinct("customer_id").alias("customers"))
        .filter(F.col("customers") > 1)
    )
    key = F.col("transaction_id").cast("string")
    return dupes.select(
        F.sha1(F.concat_ws("|", F.lit(SHARED_CLASS), key)).alias("exception_id"),
        F.lit(SHARED_CLASS).alias("class"),
        key.alias("natural_key"),
        F.lit(SHARED_DATASET).alias("dataset_id"),
        F.format_string("customers=%s", F.col("customers")).alias("detail"),
        F.lit(detected_at).cast("timestamp").alias("detected_at"),
    )


def coupon_mismatches(sales: DataFrame, plan: DataFrame, mapping: dict[str, str], detected_at: datetime) -> DataFrame:
    """Sales lines whose (month, canonical category) has no coupon plan row (FR-8, AC02, R13).

    Coupon status and repeated shipping are storage conventions (R17) and are
    never criteria here: only the plan join decides. The line's coupon status is
    copied into detail so the steward can count Used lines (BR14).
    """
    from pyspark.sql import functions as F

    dated = sales.withColumn("_month", F.month("transaction_date_iso")).withColumn(
        "_canonical", canonical_expr(F.col("product_category"), mapping)
    )
    plan_keys = plan.select(F.col("month").alias("_p_month"), F.col("product_category").alias("_p_category"))
    missing = dated.join(
        plan_keys,
        (F.col("_month") == F.col("_p_month")) & (F.col("_canonical") == F.col("_p_category")),
        "left_anti",
    )
    return missing.select(
        F.sha1(F.concat_ws("|", F.lit(MISMATCH_CLASS), F.col("sales_line_id"))).alias("exception_id"),
        F.lit(MISMATCH_CLASS).alias("class"),
        F.col("sales_line_id").alias("natural_key"),
        F.lit(MISMATCH_DATASET).alias("dataset_id"),
        F.format_string(
            "month=%s; category=%s; coupon_status=%s", F.col("_month"), F.col("_canonical"), F.col("coupon_status")
        ).alias("detail"),
        F.lit(detected_at).cast("timestamp").alias("detected_at"),
    )
