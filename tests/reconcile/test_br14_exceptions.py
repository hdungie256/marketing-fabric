"""BR14 exceptions reconcile: mart_shared_v.exceptions matches independent raw SQL.

Compares the shared list against recomputation straight from raw sources
plus Python sha1 ids, as data_steward through the policy view.
"""

import hashlib
import os

import psycopg
import pytest

pytest.importorskip("pyspark")
from pipelines import io  # noqa: E402
from pipelines.jobs.unified._common import load_mapping  # noqa: E402

VIEW = "mart_shared_v.exceptions"
MARKS = {"shared_transaction_id": 1319, "coupon_plan_mismatch": 400}


def expected() -> dict[str, dict]:
    from pyspark.sql import functions as F

    from pipelines.jobs.unified._common import canonical_expr

    sales = io.read_raw("raw/sales/sales_lines")
    plan = io.read_raw("raw/promotion/coupon_plan")
    months = {m: i for i, m in enumerate(["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"], 1)}
    plan = plan.withColumn("month", F.create_map(*[F.lit(x) for kv in months.items() for x in kv])[F.initcap(F.trim("month"))])
    canonical = canonical_expr(F.col("product_category"), load_mapping())
    shared = (
        sales.groupBy("transaction_id")
        .agg(F.countDistinct("customer_id").alias("customers"))
        .filter(F.col("customers") > 1)
        .select(F.col("transaction_id").cast("string").alias("natural_key"))
        .withColumn("class", F.lit("shared_transaction_id"))
    )
    mismatch = (
        sales.withColumn("_canonical", canonical)
        .join(
            plan.select("month", F.col("product_category").alias("plan_category")),
            (F.month("transaction_date_iso") == F.col("month")) & (F.col("_canonical") == F.col("plan_category")),
            "left_anti",
        )
        .select(F.col("sales_line_id").alias("natural_key"))
        .withColumn("class", F.lit("coupon_plan_mismatch"))
    )
    out = {}
    for row in shared.unionByName(mismatch).collect():
        out[row["natural_key"], row["class"]] = hashlib.sha1(
            f"{row['class']}|{row['natural_key']}".encode()
        ).hexdigest()
    return out


def actual() -> dict[tuple[str, str], str]:
    with psycopg.connect(os.environ["SERVING_DB_DSN"]) as conn, conn.transaction(force_rollback=True):
        conn.execute("SET LOCAL ROLE data_steward")
        cursor = conn.execute(
            f"SELECT class, natural_key, exception_id FROM {VIEW} WHERE class IN ('shared_transaction_id', 'coupon_plan_mismatch')"
        )
        return {(r[1], r[0]): r[2] for r in cursor.fetchall()}


def test_shared_list_matches_raw_recomputation():
    want, got = expected(), actual()
    assert set(want) == set(got)
    assert got == want
    counts: dict[str, int] = {}
    for _, cls in got:
        counts[cls] = counts.get(cls, 0) + 1
    for cls, mark in MARKS.items():
        assert counts.get(cls, 0) == mark, (cls, counts.get(cls, 0))
