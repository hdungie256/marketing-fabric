from __future__ import annotations

from typing import TYPE_CHECKING

from pipelines.jobs.unified._common import order_key_expr

if TYPE_CHECKING:
    from pyspark.sql import DataFrame


def build_customers(crm: DataFrame, sales: DataFrame) -> DataFrame:
    """Unify CRM profiles with first observed purchase in 2019 (R9).

    Keeps every CRM row (left join): customers without a 2019 order get
    a null first_observed_order_date and order_count 0.
    """
    from pyspark.sql import functions as F

    observed = (
        sales.withColumn("order_key", order_key_expr())
        .groupBy("customer_id")
        .agg(
            F.min("transaction_date_iso").alias("first_observed_order_date"),
            F.countDistinct("order_key").cast("int").alias("order_count"),
        )
    )
    return (
        crm.join(observed, "customer_id", "left")
        .withColumn("order_count", F.coalesce(F.col("order_count"), F.lit(0)).cast("int"))
        .select(
            "customer_id",
            "gender",
            "location",
            "tenure_months",
            "first_observed_order_date",
            "order_count",
            "provenance",
        )
    )
