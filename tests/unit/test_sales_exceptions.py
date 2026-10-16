"""Story 3.3 Spark tests: stable exception IDs, both classes, R13/R17 semantics."""

import datetime
from decimal import Decimal

import pytest

from pipelines.jobs.unified.sales_exceptions import transforms

pyspark_sql = pytest.importorskip("pyspark.sql")

SALES_SCHEMA = (
    "sales_line_id STRING, transaction_id LONG, customer_id LONG, transaction_date_iso DATE, "
    "product_category STRING, quantity INT, avg_price DECIMAL(18,2), delivery_charges DECIMAL(18,2), "
    "coupon_status STRING, provenance STRING"
)
PLAN_SCHEMA = "month INT, product_category STRING, coupon_code STRING, discount_pct INT, provenance STRING"
AT = datetime.datetime(2026, 10, 8, tzinfo=datetime.UTC)
MAPPING = {"Notebooks": "Notebooks & Journals"}


@pytest.fixture(scope="module")
def spark():
    session = pyspark_sql.SparkSession.builder.master("local[1]").appName("exceptions-3.3").getOrCreate()
    yield session
    session.stop()


def line(sid, txn, cust, date, cat, coupon="Not Used"):
    return (sid, txn, cust, date, cat, 1, Decimal("10.00"), Decimal("2.00"), coupon, "original")


@pytest.fixture(scope="module")
def sales(spark):
    rows = [
        line("L1", 100, 1, datetime.date(2019, 3, 1), "Apparel"),
        line("L2", 100, 2, datetime.date(2019, 3, 1), "Apparel", "Used"),
        line("L3", 200, 1, datetime.date(2019, 4, 1), "Fun", "Used"),
        line("L4", 300, 3, datetime.date(2019, 5, 1), "Notebooks & Journals"),
    ]
    return spark.createDataFrame(rows, SALES_SCHEMA)


@pytest.fixture(scope="module")
def plan(spark):
    return spark.createDataFrame(
        [
            (3, "Apparel", "SALE", 10, "original"),
            (3, "Notebooks & Journals", "NOTE", 5, "original"),
            (5, "Notebooks & Journals", "NOTE5", 5, "original"),
        ],
        PLAN_SCHEMA,
    )


def test_shared_codes_need_multiple_customers(spark, sales):
    found = {r.natural_key: r for r in transforms.shared_transaction_ids(sales, AT).collect()}
    assert set(found) == {"100"}
    assert found["100"].dataset_id == "unified/orders"
    assert "customers=2" in found["100"].detail


def test_exception_ids_match_python_sha1_and_survive_reruns(spark, sales):
    first = sorted(r.exception_id for r in transforms.shared_transaction_ids(sales, AT).collect())
    second = sorted(r.exception_id for r in transforms.shared_transaction_ids(sales, AT).collect())
    assert first == second
    assert first == [transforms.exception_id(transforms.SHARED_CLASS, "100")]


def test_mismatch_is_plan_join_only(spark, sales, plan):
    found = {r.natural_key: r for r in transforms.coupon_mismatches(sales, plan, MAPPING, AT).collect()}
    # L3 Fun is absent from the plan even though it is Used: still an exception (R17).
    # L4 matches after the Notebooks & Journals normalization (R13).
    assert set(found) == {"L3"}
    assert found["L3"].dataset_id == "unified/order_lines"
    assert "category=Fun" in found["L3"].detail


def test_merge_unions_classes_with_provenance(spark, sales, plan):
    from pipelines.jobs.marts.shared.exceptions import transforms as merge_t

    shared = transforms.shared_transaction_ids(sales, AT)
    mismatch = transforms.coupon_mismatches(sales, plan, MAPPING, AT)
    merged = merge_t.merge(shared, mismatch)
    assert merged.count() == 2
    assert {r["class"] for r in merged.collect()} == {transforms.SHARED_CLASS, transforms.MISMATCH_CLASS}
    assert {r.provenance for r in merged.collect()} == {"original"}
