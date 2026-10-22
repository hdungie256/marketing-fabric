"""BR05 reconcile: mart_customer_v.rfm segment totals and frequency-by-order (T-BR05)."""

import os

import psycopg
import pytest

pytest.importorskip("pyspark")
from pipelines import io  # noqa: E402

VIEW = "mart_customer_v.rfm"
DSN = os.environ.get("SERVING_DB_DSN", "")


def as_role(login, query, params=()):
    with psycopg.connect(DSN) as conn, conn.transaction(force_rollback=True):
        conn.execute(f"SET LOCAL ROLE {login}")
        return conn.execute(query, params).fetchall()


def expected_buyers() -> set[int]:
    orders = io.read_delta("unified/orders")
    return {r.customer_id for r in orders.select("customer_id").distinct().collect()}


def test_segment_totals_equal_buyers_and_frequency_reconciles():
    want = expected_buyers()
    # customer_id is a tagged identifier, so the policy view returns it as text even for the role that may see it.
    rows = as_role("crm_marketing", f"SELECT customer_id, segment, frequency_orders FROM {VIEW}")
    got = [(int(c), segment, f) for c, segment, f in rows]
    assert {r[0] for r in got} == want
    orders = io.read_delta("unified/orders")
    freq = {r.customer_id: r.n for r in orders.groupBy("customer_id").count().withColumnRenamed("count", "n").collect()}
    assert all(f == freq[c] for c, _, f in got)
    assert {r[1] for r in got} <= {
        "Champions",
        "Can't Lose",
        "At Risk",
        "Loyal",
        "Potential Loyalist",
        "Recent First Buyers",
        "Needs Attention",
        "Hibernating",
        "Lost",
    }
