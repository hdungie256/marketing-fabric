from datetime import date
from decimal import Decimal

import pytest

from pipelines.jobs.marts.campaign.product_sales import transforms

pytest.importorskip("pyspark.sql")

LINES = (
    "order_key string, transaction_date_iso date, product_sku string, product_description string, "
    "product_category string, quantity int, line_gross_value decimal(18,2), provenance string"
)
ATTRIBUTION = "order_key string, campaign_id string, provenance string"
CATEGORY_MAP = "raw_category string, canonical_category string"
CAMPAIGNS = "campaign_id string, campaign_name string"
JAN, FEB = date(2019, 1, 16), date(2019, 2, 5)


def frames(spark, lines, attribution=None, categories=("Apparel", "Drinkware", "Nest", "Nest-USA", "Nest-Canada")):
    return (
        spark.createDataFrame(lines, LINES),
        spark.createDataFrame(attribution or [("O1", "CMP19_01", "synthetic")], ATTRIBUTION),
        spark.createDataFrame([(c, c) for c in categories], CATEGORY_MAP),
        spark.createDataFrame([("CMP19_01", "New-year Apparel")], CAMPAIGNS),
    )


def rows(df):
    return {(r.month, r.campaign_id, r.product_sku): r for r in df.collect()}


def two_lines():
    return [
        ("O1", JAN, "SKU-A", "Shirt", "Apparel", 2, Decimal("20.00"), "original"),
        ("O1", JAN, "SKU-D", "Mug", "Drinkware", 1, Decimal("5.00"), "original"),
    ]


def test_campaign_rows_take_every_line_of_attributed_orders(spark):
    got = rows(transforms.build(*frames(spark, two_lines())))
    a = got[(date(2019, 1, 1), "CMP19_01", "SKU-A")]
    assert (a.gross_value, a.quantity) == (Decimal("20.00"), 2)
    assert got[(date(2019, 1, 1), "CMP19_01", "SKU-D")].gross_value == Decimal("5.00")


def test_all_rows_include_unattributed_lines(spark):
    lines = two_lines() + [("O2", JAN, "SKU-A", "Shirt", "Apparel", 1, Decimal("10.00"), "original")]
    got = rows(transforms.build(*frames(spark, lines)))
    total = got[(date(2019, 1, 1), "ALL", "SKU-A")]
    assert (total.gross_value, total.quantity, total.campaign_name) == (Decimal("30.00"), 3, "All campaigns")
    assert got[(date(2019, 1, 1), "CMP19_01", "SKU-A")].gross_value == Decimal("20.00")


def test_nest_categories_stay_separate(spark):
    lines = [("O1", JAN, f"SKU-{c}", c, c, 1, Decimal("1.00"), "original") for c in ("Nest", "Nest-USA", "Nest-Canada")]
    df = transforms.build(*frames(spark, lines))
    assert {r.canonical_category for r in df.collect()} == {"Nest", "Nest-USA", "Nest-Canada"}


def test_month_buckets_and_provenance(spark):
    lines = two_lines() + [("O2", FEB, "SKU-A", "Shirt", "Apparel", 1, Decimal("10.00"), "original")]
    got = rows(transforms.build(*frames(spark, lines)))
    assert {k[0] for k in got} == {date(2019, 1, 1), date(2019, 2, 1)}
    assert got[(date(2019, 1, 1), "CMP19_01", "SKU-A")].provenance == "synthetic"
    assert got[(date(2019, 1, 1), "ALL", "SKU-A")].provenance == "original"


def test_columns_follow_contract_order(spark):
    from fabric_control.contracts import columns, load_schema

    df = transforms.build(*frames(spark, two_lines()))
    names = [n for n, _ in columns(load_schema("mart_campaign.product_sales")) if not n.startswith("_")]
    assert df.columns == names


def test_product_rules_pass_and_fail(spark):
    from pipelines.jobs.marts.campaign.product_sales.job import product_rules

    lines = two_lines() + [
        ("O2", JAN, "SKU-A", "Shirt", "Apparel", 1, Decimal("10.00"), "original"),
        ("O3", JAN, "SKU-N", "Nest", "Nest-Canada", 1, Decimal("3.00"), "original"),
    ]
    line_df, attribution, category_map, campaigns = frames(spark, lines)
    sales = transforms.build(line_df, attribution, category_map, campaigns)
    assert all(r.passed for r in product_rules(sales, line_df))

    def failed(df):
        return {r.rule_id for r in product_rules(df, line_df) if not r.passed}

    assert "all_gross_matches_lines" in failed(sales.filter("NOT (campaign_id = 'ALL' AND product_sku = 'SKU-D')"))
    over = sales.filter("campaign_id = 'CMP19_01'").withColumn("gross_value", sales.gross_value + 100)
    assert "campaign_not_above_all" in failed(sales.filter("campaign_id = 'ALL'").unionByName(over))
    assert "nest_categories_separate" in failed(sales.filter("canonical_category <> 'Nest-Canada'"))
