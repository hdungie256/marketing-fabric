from datetime import date
from decimal import Decimal

import pytest

from pipelines.jobs.marts.campaign.campaign_overview import transforms as overview
from pipelines.jobs.marts.campaign.comparison import transforms

pytest.importorskip("pyspark.sql")

DAILY = "campaign_id string, date date, attributed_orders int, attributed_gross_value decimal(18,2), provenance string"
ORDERS = "campaign_id string, date date, customer_id long, provenance string"
CAMPAIGNS = "campaign_id string, campaign_name string, channel string, provenance string"
JAN16, JAN17, MAR10 = date(2019, 1, 16), date(2019, 1, 17), date(2019, 3, 10)


def frames(spark):
    daily = spark.createDataFrame(
        [
            ("CMP19_01", JAN16, 1, Decimal("10.00"), "synthetic"),
            ("CMP19_04", JAN17, 1, Decimal("20.00"), "synthetic"),
            ("CMP19_02", MAR10, 2, Decimal("30.00"), "synthetic"),
        ],
        DAILY,
    )
    orders = spark.createDataFrame(
        [
            ("CMP19_01", JAN16, 7, "synthetic"),
            ("CMP19_04", JAN17, 7, "synthetic"),
            ("CMP19_02", MAR10, 8, "synthetic"),
            ("CMP19_02", MAR10, 9, "synthetic"),
        ],
        ORDERS,
    )
    campaigns = spark.createDataFrame(
        [
            ("CMP19_01", "New-year Apparel", "Paid Search", "synthetic"),
            ("CMP19_02", "Spring Nest", "Paid Social", "synthetic"),
            ("CMP19_04", "Autumn Search", "Paid Search", "synthetic"),
        ],
        CAMPAIGNS,
    )
    return daily, orders, campaigns


def rows(spark):
    return {(r.period_id, r.compare_by, r.group_id): r for r in transforms.build(*frames(spark)).collect()}


def test_channel_buyers_distinct_across_campaigns(spark):
    got = rows(spark)
    channel = got[("FY2019", "channel", "Paid Search")]
    assert (channel.attributed_buyers, channel.attributed_orders) == (1, 2)
    assert got[("FY2019", "campaign", "CMP19_01")].attributed_buyers == 1
    assert got[("FY2019", "campaign", "CMP19_04")].attributed_buyers == 1
    assert (channel.group_name, channel.channel) == ("Paid Search", "Paid Search")


def test_campaign_rows_match_overview_build(spark):
    daily, orders, campaigns = frames(spark)
    want = {
        (r.period_id, r.campaign_id): r
        for r in overview.build(daily, orders, campaigns.select("campaign_id", "campaign_name", "provenance")).collect()
    }
    for (period, kind, group), row in rows(spark).items():
        if kind != "campaign":
            continue
        ref = want[(period, group)]
        assert (row.attributed_orders, row.attributed_buyers, row.attributed_gross_value, row.average_order_value) == (
            ref.attributed_orders,
            ref.attributed_buyers,
            ref.attributed_gross_value,
            ref.average_order_value,
        )


def test_full_grid_includes_empty_channels(spark):
    got = rows(spark)
    assert len(got) == 5 * (3 + 2)
    empty = got[("2019-Q2", "channel", "Paid Social")]
    assert (empty.attributed_orders, empty.attributed_buyers, empty.attributed_gross_value) == (0, 0, Decimal("0.00"))
    assert empty.average_order_value is None


def test_columns_follow_contract_order(spark):
    from fabric_control.contracts import columns, load_schema

    names = [n for n, _ in columns(load_schema("mart_campaign.comparison")) if not n.startswith("_")]
    assert transforms.build(*frames(spark)).columns == names


def test_rules_fail_when_channel_orders_drift(spark):
    from pyspark.sql import functions as F

    from pipelines.jobs.marts.campaign.comparison.job import comparison_rules

    daily, orders, campaigns = frames(spark)
    df = transforms.build(daily, orders, campaigns)
    assert all(r.passed for r in comparison_rules(df, daily, campaigns))
    drift = F.col("period_id").eqNullSafe("FY2019") & (F.col("group_id") == "Paid Search")
    bumped = df.withColumn(
        "attributed_orders", F.when(drift, F.col("attributed_orders") + 1).otherwise(F.col("attributed_orders"))
    )
    assert "campaign_orders_equal_channel_orders" in {
        r.rule_id for r in comparison_rules(bumped, daily, campaigns) if not r.passed
    }
    dropped = df.filter("NOT (period_id = 'FY2019' AND group_id = 'Paid Search')")
    assert "full_grid" in {r.rule_id for r in comparison_rules(dropped, daily, campaigns) if not r.passed}
