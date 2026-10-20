"""Story 5.1 Spark tests: quintiles, deterministic ties, segment rules, mart build."""

import datetime
from decimal import Decimal
from pathlib import Path

import pytest
import yaml

from pipelines.jobs.marts.customer.rfm import transforms as rfm

pyspark_sql = pytest.importorskip("pyspark.sql")

ROOT = Path(__file__).resolve().parents[2]
RULES = yaml.safe_load((ROOT / "governance" / "mappings" / "rfm_segments.yml").read_text())["segments"]

ORDERS_SCHEMA = "order_key STRING, customer_id LONG, order_date DATE, gross_value DECIMAL(18,2)"
CUSTOMERS_SCHEMA = "customer_id LONG, gender STRING, location STRING, tenure_months INT, provenance STRING"
LINES_SCHEMA = "customer_id LONG, order_key STRING, canonical_category STRING"


@pytest.fixture(scope="module")
def spark():
    session = pyspark_sql.SparkSession.builder.master("local[1]").appName("rfm-5.1").getOrCreate()
    yield session
    session.stop()


def orders_frame(spark, specs):
    rows = []
    for cid, days_ago, n_orders, value in specs:
        date = datetime.date(2019, 12, 31) - datetime.timedelta(days=days_ago)
        for i in range(n_orders):
            rows.append((f"{cid}|{i}", cid, date, Decimal(str(value))))
    return spark.createDataFrame(rows, ORDERS_SCHEMA)


def test_quintile_scores_top_bucket_five_and_breaks_ties_by_customer(spark):
    df = spark.createDataFrame([(1, 10), (2, 20), (3, 30), (4, 40), (5, 50)], "customer_id LONG, v INT")
    scored = {r.customer_id: r.s for r in rfm.quintile(df, [pyspark_sql.functions.col("v").desc()], "s").collect()}
    assert scored == {1: 1, 2: 2, 3: 3, 4: 4, 5: 5}
    tied = spark.createDataFrame([(2, 10), (1, 10)], "customer_id LONG, v INT")
    order = [pyspark_sql.functions.col("v").asc(), pyspark_sql.functions.col("customer_id").asc()]
    first = {r.customer_id: r.s for r in rfm.quintile(tied, order, "s").collect()}
    assert first[1] >= first[2]


def test_assign_segment_covers_all_nine_with_first_match_wins(spark):
    rows = [
        (5, 5, 5, "Champions"),
        (1, 5, 5, "Can't Lose"),
        (2, 3, 1, "At Risk"),
        (3, 5, 5, "Loyal"),
        (5, 2, 1, "Potential Loyalist"),
        (4, 1, 5, "Recent First Buyers"),
        (3, 1, 1, "Needs Attention"),
        (2, 1, 1, "Hibernating"),
        (1, 1, 1, "Lost"),
    ]
    df = spark.createDataFrame(rows, "recency_score INT, frequency_score INT, monetary_score INT, want STRING")
    got = {
        (r.recency_score, r.frequency_score, r.monetary_score): r.segment
        for r in rfm.assign_segment(df, RULES).collect()
    }
    assert all(got[(r, f, m)] == want for r, f, m, want in rows)


def test_rule_table_order_is_authoritative():
    assert [r["name"] for r in RULES] == rfm.SEGMENT_ORDER


def test_build_rfm_end_to_end_is_deterministic(spark):
    specs = [(1, 5, 6, 100), (2, 40, 2, 50), (3, 200, 1, 20), (4, 10, 3, 200), (5, 300, 1, 10)]
    orders = orders_frame(spark, specs)
    customers = spark.createDataFrame([(cid, "M", "Hanoi", 12, "original") for cid, _, _, _ in specs], CUSTOMERS_SCHEMA)
    lines = spark.createDataFrame(
        [(cid, f"{cid}|0", "Apparel") for cid, _, _, _ in specs] + [(1, "1|1", "Notebooks & Journals")],
        LINES_SCHEMA,
    )

    def by_customer(d):
        return d["customer_id"]

    first = [r.asDict() for r in rfm.build_rfm(orders, customers, lines, "2019-12-31", RULES).collect()]
    second = [r.asDict() for r in rfm.build_rfm(orders, customers, lines, "2019-12-31", RULES).collect()]
    assert sorted(first, key=by_customer) == sorted(second, key=by_customer)
    by_id = {r["customer_id"]: r for r in first}
    assert set(by_id) == {1, 2, 3, 4, 5}
    assert by_id[1]["recency_days"] == 5
    assert by_id[1]["frequency_orders"] == 6
    assert abs(float(by_id[1]["monetary_value"]) - 600.00) < 1e-9
    assert by_id[1]["categories"] == "Apparel,Notebooks & Journals"
    assert by_id[1]["provenance"] == "original"
    assert all(1 <= r["recency_score"] <= 5 for r in first)
    assert all(r["segment"] in rfm.SEGMENT_ORDER for r in first)


def test_build_rfm_keeps_buyers_missing_from_crm(spark):
    orders = orders_frame(spark, [(9, 5, 1, 10)])
    customers = spark.createDataFrame([], CUSTOMERS_SCHEMA)
    lines = spark.createDataFrame([(9, "9|0", "Apparel")], LINES_SCHEMA)
    row = rfm.build_rfm(orders, customers, lines, "2019-12-31", RULES).first()
    assert row.customer_id == 9
    assert row.gender is None
