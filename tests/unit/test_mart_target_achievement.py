from datetime import date
from decimal import Decimal

import pytest

from pipelines.jobs.marts.campaign.target_achievement import transforms

pytest.importorskip("pyspark.sql")

TARGETS = (
    "campaign_id string, target_metric string, target_value decimal(18,2), "
    "evaluation_from date, evaluation_through date, target_note string, provenance string, provenance_note string"
)
CAMPAIGNS = "campaign_id string, campaign_name string, provenance string"
DAILY = (
    "campaign_id string, date date, attributed_orders int, attributed_gross_value decimal(18,2), "
    "buyers int, first_observed_buyers int, provenance string"
)
SPEND = "campaign_id string, date date, allocated decimal(18,2), provenance string"
FROM, THROUGH, AFTER = date(2019, 5, 1), date(2019, 5, 31), date(2019, 6, 1)
GROSS, ORDERS, BUYERS = "Gross item value", "Attributed order count", "First observed buyer count"


def target(cid, metric, value):
    return (cid, metric, Decimal(value), FROM, THROUGH, "n", "synthetic", "n")


def day(cid, d, orders=0, gross="0", buyers=0):
    return (cid, d, orders, Decimal(gross), buyers, buyers, "synthetic")


def build(spark, targets, daily=(), spend=(), scope=None):
    t = spark.createDataFrame(targets, TARGETS)
    c = spark.createDataFrame([(r[0], f"Name {r[0]}", "synthetic") for r in targets], CAMPAIGNS)
    d = spark.createDataFrame(list(daily), DAILY)
    s = spark.createDataFrame(list(spend), SPEND)
    if scope:
        t, c, d, s = (transforms.narrow(x, scope) for x in (t, c, d, s))
    return {r.campaign_id: r for r in transforms.build(t, c, d, s).collect()}


def test_actual_uses_each_campaigns_own_metric(spark):
    rows = build(
        spark,
        [target("CMP19_01", GROSS, "25923.17"), target("CMP19_02", ORDERS, "495"), target("CMP19_03", BUYERS, "40")],
        [day(c, FROM, orders=442, gross="28177.36", buyers=28) for c in ("CMP19_01", "CMP19_02", "CMP19_03")],
    )
    assert {c: r.target_metric for c, r in rows.items()} == {
        "CMP19_01": "attributed_gross_value",
        "CMP19_02": "attributed_orders",
        "CMP19_03": "first_observed_buyers",
    }
    assert rows["CMP19_03"].actual == Decimal("28.00")
    assert rows["CMP19_01"].actual == Decimal("28177.36")
    assert rows["CMP19_02"].actual == Decimal("442.00")
    assert rows["CMP19_01"].provenance == "synthetic"


@pytest.mark.parametrize(
    "actual,tgt,expected",
    [(6999, 10000, "stop"), (7000, 10000, "adjust"), (9999, 10000, "adjust"), (10000, 10000, "continue")],
)
def test_threshold_boundaries(spark, actual, tgt, expected):
    row = build(spark, [target("A", ORDERS, str(tgt))], [day("A", FROM, orders=actual)])["A"]
    assert row.recommendation == expected


def test_threshold_uses_unrounded_ratio(spark):
    # 0.6999996 rounds to 0.700000 at decimal(9,6) but is still below 0.7
    row = build(spark, [target("A", ORDERS, "10000000")], [day("A", FROM, orders=6999996)])["A"]
    assert row.recommendation == "stop"


def test_window_excludes_outside_rows(spark):
    rows = build(
        spark,
        [target("A", ORDERS, "10")],
        [day("A", THROUGH, orders=3), day("A", AFTER, orders=50), day("A", date(2019, 4, 30), orders=50)],
        [("A", THROUGH, Decimal("5"), "synthetic"), ("A", AFTER, Decimal("99"), "synthetic")],
    )
    assert rows["A"].actual == Decimal("3.00")
    assert rows["A"].allocated_spend == Decimal("5.00")


def test_allocated_spend_summed_over_window(spark):
    spend = [("A", FROM, Decimal("1.50"), "synthetic"), ("A", THROUGH, Decimal("2.25"), "synthetic")]
    assert build(spark, [target("A", ORDERS, "10")], spend=spend)["A"].allocated_spend == Decimal("3.75")


def test_no_sales_is_stop(spark):
    rows = build(spark, [target("A", ORDERS, "10")])
    assert len(rows) == 1
    r = rows["A"]
    assert (r.actual, r.achievement, r.recommendation, r.allocated_spend) == (
        Decimal("0.00"),
        Decimal("0.000000"),
        "stop",
        Decimal("0.00"),
    )


def test_unknown_metric_raises(spark):
    with pytest.raises(ValueError, match="Revenue per visit"):
        build(spark, [target("A", "Revenue per visit", "10")])


def test_scope_ignores_date(spark):
    targets = [target("CMP19_03", BUYERS, "40"), target("CMP19_04", BUYERS, "40")]
    daily = [day("CMP19_03", FROM, buyers=10), day("CMP19_03", date(2019, 5, 20), buyers=18), day("CMP19_04", FROM, buyers=1)]
    scope = {"mode": "scope", "keys": {"campaign_id": ["CMP19_03"], "date": ["2019-05-20"]}}
    narrowed = build(spark, targets, daily, scope=scope)
    assert list(narrowed) == ["CMP19_03"]
    assert narrowed["CMP19_03"] == build(spark, targets, daily)["CMP19_03"]


def test_narrow_is_noop_on_full_or_missing_campaign_key(spark):
    df = spark.createDataFrame([target("A", ORDERS, "1"), target("B", ORDERS, "1")], TARGETS)
    assert transforms.narrow(df, {"mode": "full"}).count() == 2
    assert transforms.narrow(df, {"mode": "scope", "keys": {"date": ["2019-05-20"]}}).count() == 2


def test_columns_follow_contract_order(spark):
    from fabric_control.contracts import columns, load_schema

    names = [n for n, _ in columns(load_schema("mart_campaign.target_achievement")) if not n.startswith("_")]
    t = spark.createDataFrame([target("A", ORDERS, "1")], TARGETS)
    c = spark.createDataFrame([("A", "n", "synthetic")], CAMPAIGNS)
    out = transforms.build(t, c, spark.createDataFrame([], DAILY), spark.createDataFrame([], SPEND))
    assert out.columns == names


def rule_frames(spark):
    targets = [target("A", ORDERS, "10"), target("B", ORDERS, "10")]
    t = spark.createDataFrame(targets, TARGETS)
    c = spark.createDataFrame([(r[0], f"Name {r[0]}", "synthetic") for r in targets], CAMPAIGNS)
    d = spark.createDataFrame([day("A", FROM, orders=7), day("B", FROM, orders=10)], DAILY)
    return t, transforms.build(t, c, d, spark.createDataFrame([], SPEND))


def failed(rules):
    return {r.rule_id for r in rules if not r.passed}


def test_rules_pass_on_built_output(spark):
    from pipelines.jobs.marts.campaign.target_achievement.job import target_rules

    t, df = rule_frames(spark)
    assert failed(target_rules(df, t)) == set()


def test_rules_fail_when_recommendation_disagrees(spark):
    from pyspark.sql import functions as F

    from pipelines.jobs.marts.campaign.target_achievement.job import target_rules

    t, df = rule_frames(spark)
    flipped = df.withColumn("recommendation", F.when(F.col("campaign_id") == "A", "stop").otherwise(F.col("recommendation")))
    assert failed(target_rules(flipped, t)) == {"recommendation_matches_thresholds"}


def test_rules_fail_on_missing_target_row(spark):
    from pipelines.jobs.marts.campaign.target_achievement.job import target_rules

    t, df = rule_frames(spark)
    assert failed(target_rules(df.filter("campaign_id <> 'B'"), t)) == {"one_row_per_target"}
