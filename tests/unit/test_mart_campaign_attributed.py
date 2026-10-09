from datetime import date
from decimal import Decimal

import pytest

from pipelines.jobs.marts.shared.campaign_attributed_daily import transforms
from tests.unit.unified_fixtures import contract, frame, schema

pytest.importorskip("pyspark.sql")

ORDERS_MART = "mart_shared.campaign_attributed_orders"
DAILY_MART = "mart_shared.campaign_attributed_daily"
D1, D2 = date(2019, 1, 16), date(2019, 1, 17)


def link(customer_id, transaction_id, campaign_id="CMP19_01", day=D1, provenance="synthetic"):
    return (
        f"{customer_id}|{transaction_id}",
        customer_id,
        transaction_id,
        f"C{customer_id}_T{transaction_id}",
        day,
        campaign_id,
        "Apparel",
        "Apparel",
        "TARGET_CATEGORY_PURCHASE_SAMPLE",
        provenance,
        "SYNTHETIC; no ad exposure evidence",
    )


def order(customer_id, transaction_id, gross="10.00", shipping="5.00", day=D1):
    return (
        f"{customer_id}|{transaction_id}",
        customer_id,
        transaction_id,
        f"C{customer_id}_T{transaction_id}",
        day,
        Decimal(gross),
        Decimal(shipping),
        1,
        "source",
    )


def customer(customer_id, first=D1):
    return (customer_id, "F", "Chicago", 12, first, 3, "source")


def inputs(spark, links, orders, customers):
    return (
        frame(spark, "unified/attribution", links),
        frame(spark, "unified/orders", orders),
        frame(spark, "unified/customers", customers),
    )


def per_order(spark, links, orders, customers):
    return transforms.attributed_orders(*inputs(spark, links, orders, customers))


def business(dataset_id):
    return [(name, kind) for name, kind in contract(dataset_id) if not name.startswith("_")]


def test_order_table_matches_contract(spark):
    df = per_order(spark, [link(1, 1)], [order(1, 1)], [customer(1)])
    assert schema(df) == business(ORDERS_MART)


def test_daily_table_matches_contract(spark):
    df = transforms.daily(per_order(spark, [link(1, 1)], [order(1, 1)], [customer(1)]))
    assert schema(df) == business(DAILY_MART)


def test_first_observed_follows_first_order_date(spark):
    df = per_order(spark, [link(1, 1, day=D1), link(1, 2, day=D2)], [order(1, 1), order(1, 2)], [customer(1, D1)])
    assert {r.order_key: r.is_first_observed for r in df.collect()} == {"1|1": True, "1|2": False}


def test_null_first_observed_date_is_false(spark):
    df = per_order(spark, [link(1, 1)], [order(1, 1)], [customer(1, None)])
    assert df.collect()[0].is_first_observed is False


def test_gross_value_excludes_shipping(spark):
    df = per_order(spark, [link(1, 1)], [order(1, 1, gross="10.00", shipping="5.00")], [customer(1)])
    assert df.collect()[0].gross_value == Decimal("10.00")


def test_two_orders_same_day_count_one_buyer(spark):
    df = transforms.daily(
        per_order(spark, [link(1, 1), link(1, 2)], [order(1, 1), order(1, 2, gross="2.50")], [customer(1)])
    )
    row = df.collect()[0]
    assert (row.attributed_orders, row.buyers, row.first_observed_buyers) == (2, 1, 1)
    assert row.attributed_gross_value == Decimal("12.50")


def test_buyers_are_per_day_not_per_period(spark):
    orders_df = per_order(
        spark, [link(1, 1, day=D1), link(1, 2, day=D2)], [order(1, 1), order(1, 2)], [customer(1, D1)]
    )
    by_day = {r.date: (r.buyers, r.first_observed_buyers) for r in transforms.daily(orders_df).collect()}
    assert by_day == {D1: (1, 1), D2: (1, 0)}
    assert orders_df.select("customer_id").distinct().count() == 1


def test_daily_sums_back_to_order_rows(spark):
    links = [link(1, 1), link(2, 2, campaign_id="CMP19_02"), link(3, 3, day=D2)]
    orders_df = per_order(
        spark, links, [order(1, 1), order(2, 2), order(3, 3)], [customer(1), customer(2), customer(3)]
    )
    total = transforms.daily(orders_df).agg({"attributed_orders": "sum"}).first()[0]
    assert total == orders_df.count() == 3


def test_any_synthetic_order_marks_the_day_synthetic(spark):
    links = [link(1, 1, provenance="source"), link(2, 2, provenance="synthetic")]
    df = transforms.daily(per_order(spark, links, [order(1, 1), order(2, 2)], [customer(1), customer(2)]))
    assert df.collect()[0].provenance == "synthetic"


def test_missing_order_and_customer_are_detected(spark):
    attribution, orders_df, customers_df = inputs(spark, [link(1, 1), link(2, 2)], [order(1, 1)], [customer(1)])
    assert [r.order_key for r in transforms.missing_orders(attribution, orders_df).collect()] == ["2|2"]
    assert [r.customer_id for r in transforms.missing_customers(attribution, customers_df).collect()] == [2]


def test_transform_is_deterministic(spark):
    links = [link(1, 1), link(1, 2, day=D2), link(2, 3, campaign_id="CMP19_02")]
    orders = [order(1, 1), order(1, 2), order(2, 3)]
    customers = [customer(1), customer(2, D2)]
    first = per_order(spark, links, orders, customers)
    second = per_order(spark, links[::-1], orders[::-1], customers[::-1])
    assert sorted(first.collect()) == sorted(second.collect())
    assert sorted(transforms.daily(first).collect()) == sorted(transforms.daily(second).collect())
