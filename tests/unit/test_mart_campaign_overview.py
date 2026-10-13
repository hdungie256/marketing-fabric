from datetime import date
from decimal import Decimal

import pytest

from pipelines.jobs.marts.campaign.campaign_overview import transforms

pytest.importorskip("pyspark.sql")

DAILY = "campaign_id string, date date, attributed_orders int, attributed_gross_value decimal(18,2), provenance string"
ORDERS = "campaign_id string, date date, customer_id long, provenance string"
CAMPAIGNS = "campaign_id string, campaign_name string, provenance string"
JAN16, JAN17, MAR10 = date(2019, 1, 16), date(2019, 1, 17), date(2019, 3, 10)


def test_periods_fy_then_quarters():
    assert transforms.periods([2019]) == [
        ("FY2019", "Jan–Dec 2019", date(2019, 1, 1), date(2019, 12, 31)),
        ("2019-Q1", "Q1 2019", date(2019, 1, 1), date(2019, 3, 31)),
        ("2019-Q2", "Q2 2019", date(2019, 4, 1), date(2019, 6, 30)),
        ("2019-Q3", "Q3 2019", date(2019, 7, 1), date(2019, 9, 30)),
        ("2019-Q4", "Q4 2019", date(2019, 10, 1), date(2019, 12, 31)),
    ]


def build(spark):
    daily = spark.createDataFrame(
        [
            ("CMP19_01", JAN16, 1, Decimal("10.00"), "synthetic"),
            ("CMP19_01", JAN17, 1, Decimal("20.00"), "synthetic"),
            ("CMP19_02", MAR10, 1, Decimal("30.00"), "synthetic"),
        ],
        DAILY,
    )
    orders = spark.createDataFrame(
        [("CMP19_01", JAN16, 7, "synthetic"), ("CMP19_01", JAN17, 7, "synthetic"), ("CMP19_02", MAR10, 7, "synthetic")],
        ORDERS,
    )
    campaigns = spark.createDataFrame(
        [("CMP19_01", "New-year Apparel", "synthetic"), ("CMP19_02", "Spring Nest", "synthetic")], CAMPAIGNS
    )
    return {(r.period_id, r.campaign_id): r for r in transforms.build(daily, orders, campaigns).collect()}


def test_buyer_counted_once_across_days_and_campaigns(spark):
    rows = build(spark)
    assert rows[("FY2019", "CMP19_01")].attributed_buyers == 1
    assert rows[("FY2019", "ALL")].attributed_buyers == 1
    assert rows[("FY2019", "ALL")].attributed_orders == 3
    assert rows[("FY2019", "ALL")].attributed_gross_value == Decimal("60.00")
    assert rows[("FY2019", "ALL")].average_order_value == Decimal("20.00")


def test_zero_cells_present_and_aov_null(spark):
    rows = build(spark)
    assert len(rows) == 5 * 3
    q2 = rows[("2019-Q2", "CMP19_01")]
    assert (q2.attributed_orders, q2.attributed_buyers, q2.attributed_gross_value) == (0, 0, Decimal("0.00"))
    assert q2.average_order_value is None
    assert q2.campaign_name == "New-year Apparel"


def test_all_row_name_and_provenance(spark):
    row = build(spark)[("2019-Q1", "ALL")]
    assert (row.campaign_name, row.provenance, row.period_label) == ("All campaigns", "synthetic", "Q1 2019")


def test_columns_follow_contract_order(spark):
    from fabric_control.contracts import columns, load_schema

    df = transforms.build(
        spark.createDataFrame([("CMP19_01", JAN16, 1, Decimal("1.00"), "original")], DAILY),
        spark.createDataFrame([("CMP19_01", JAN16, 1, "original")], ORDERS),
        spark.createDataFrame([("CMP19_01", "A", "original")], CAMPAIGNS),
    )
    names = [n for n, _ in columns(load_schema("mart_campaign.campaign_overview")) if not n.startswith("_")]
    assert df.columns == names


def test_overview_rules_pass_on_built_grid_and_fail_on_missing_row(spark):
    from pipelines.jobs.marts.campaign.campaign_overview.job import overview_rules

    daily = spark.createDataFrame([("CMP19_01", JAN16, 2, Decimal("10.00"), "synthetic")], DAILY)
    orders = spark.createDataFrame([("CMP19_01", JAN16, 7, "synthetic"), ("CMP19_01", JAN16, 8, "synthetic")], ORDERS)
    campaigns = spark.createDataFrame([("CMP19_01", "A", "synthetic")], CAMPAIGNS)
    overview = transforms.build(daily, orders, campaigns)
    assert all(r.passed for r in overview_rules(overview, daily, campaigns))
    broken = overview.filter("NOT (period_id = 'FY2019' AND campaign_id = 'ALL')")
    failed = {r.rule_id for r in overview_rules(broken, daily, campaigns) if not r.passed}
    assert failed == {"fy_orders_match_daily", "full_grid"}
