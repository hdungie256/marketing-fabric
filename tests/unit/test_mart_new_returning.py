from datetime import date

import pytest

from pipelines.jobs.marts.campaign.new_returning import transforms

pytest.importorskip("pyspark.sql")

ORDERS = "campaign_id string, date date, customer_id long, is_first_observed boolean, provenance string"
CAMPAIGNS = "campaign_id string, campaign_name string, provenance string"
JAN16, JAN17, MAR10 = date(2019, 1, 16), date(2019, 1, 17), date(2019, 3, 10)


def frames(spark):
    orders = spark.createDataFrame(
        [
            ("CMP19_01", JAN16, 7, True, "synthetic"),
            ("CMP19_01", JAN17, 7, False, "synthetic"),
            ("CMP19_02", MAR10, 7, False, "synthetic"),
        ],
        ORDERS,
    )
    campaigns = spark.createDataFrame(
        [("CMP19_01", "New-year Apparel", "synthetic"), ("CMP19_02", "Spring Nest", "synthetic")], CAMPAIGNS
    )
    return orders, campaigns


def build(spark):
    return {(r.period_id, r.campaign_id): r for r in transforms.build(*frames(spark)).collect()}


def test_buyer_counted_once_across_days_and_campaigns(spark):
    rows = build(spark)
    got = {c: (rows[("FY2019", c)].attributed_buyers, rows[("FY2019", c)].first_observed_buyers) for c in rows_ids()}
    assert got == {"CMP19_01": (1, 1), "CMP19_02": (1, 0), "ALL": (1, 1)}
    assert [rows[("FY2019", c)].returning_buyers for c in rows_ids()] == [0, 1, 0]


def rows_ids():
    return ["CMP19_01", "CMP19_02", "ALL"]


def test_identity_and_full_grid(spark):
    rows = build(spark)
    assert len(rows) == 5 * 3
    assert all(r.first_observed_buyers + r.returning_buyers == r.attributed_buyers for r in rows.values())
    assert rows[("FY2019", "ALL")].campaign_name == "All campaigns"
    assert rows[("2019-Q2", "CMP19_01")].attributed_buyers == 0


def test_columns_follow_contract_order(spark):
    from fabric_control.contracts import columns, load_schema

    names = [n for n, _ in columns(load_schema("mart_campaign.new_returning")) if not n.startswith("_")]
    assert transforms.build(*frames(spark)).columns == names


def test_rules_fail_on_broken_identity(spark):
    from pyspark.sql import functions as F

    from pipelines.jobs.marts.campaign.new_returning.job import new_returning_rules

    orders, campaigns = frames(spark)
    df = transforms.build(orders, campaigns)
    assert all(r.passed for r in new_returning_rules(df, campaigns))
    bumped = df.withColumn(
        "returning_buyers",
        F.when(
            (F.col("period_id") == "FY2019") & (F.col("campaign_id") == "ALL"), F.col("returning_buyers") + 1
        ).otherwise(F.col("returning_buyers")),
    )
    assert {r.rule_id for r in new_returning_rules(bumped, campaigns) if not r.passed} == {
        "first_plus_returning_equals_buyers"
    }
    dropped = df.filter("NOT (period_id = 'FY2019' AND campaign_id = 'ALL')")
    assert "full_grid" in {r.rule_id for r in new_returning_rules(dropped, campaigns) if not r.passed}
