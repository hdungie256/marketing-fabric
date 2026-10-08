from datetime import date
from decimal import Decimal

import pytest

from pipelines.jobs.unified.campaigns import transforms
from tests.unit.unified_fixtures import category_map, contract, frame, schema

pytest.importorskip("pyspark.sql")

NOTE = "SYNTHETIC"


def campaign(campaign_id, category):
    return (
        campaign_id,
        f"Name {campaign_id}",
        "Paid Search",
        date(2019, 1, 15),
        date(2019, 2, 10),
        category,
        "Revenue",
        Decimal("18849.59"),
        "synthetic",
        NOTE,
    )


def test_transform_matches_contract(spark):
    raw = frame(spark, "raw/campaign/campaigns", [campaign("CMP19_01", "Apparel")])
    assert schema(transforms.transform(raw, category_map(spark))) == contract("unified/campaigns")


def test_nest_variants_stay_separate(spark):
    rows = [campaign("A", "Nest"), campaign("B", "Nest-USA"), campaign("C", "Nest-Canada")]
    result = transforms.transform(frame(spark, "raw/campaign/campaigns", rows), category_map(spark))
    assert {r.campaign_id: r.target_category for r in result.collect()} == {
        "A": "Nest",
        "B": "Nest-USA",
        "C": "Nest-Canada",
    }


def test_notebooks_maps_and_keeps_source(spark):
    raw = frame(spark, "raw/campaign/campaigns", [campaign("A", "Notebooks")])
    row = transforms.transform(raw, category_map(spark)).collect()[0]
    assert (row.target_category, row.source_target_category) == ("Notebooks & Journals", "Notebooks")


def test_unmapped_category_keeps_source_value(spark):
    raw = frame(spark, "raw/campaign/campaigns", [campaign("A", "Waze")])
    assert transforms.transform(raw, category_map(spark)).collect()[0].target_category == "Waze"


def test_duplicate_map_rows_do_not_multiply_rows(spark):
    pairs = [("Notebooks", "Notebooks & Journals"), ("Notebooks", "Notebooks & Journals")]
    raw = frame(spark, "raw/campaign/campaigns", [campaign("A", "Notebooks")])
    assert transforms.transform(raw, category_map(spark, pairs)).count() == 1


def test_provenance_is_kept(spark):
    raw = frame(spark, "raw/campaign/campaigns", [campaign("A", "Apparel")])
    row = transforms.transform(raw, category_map(spark)).collect()[0]
    assert (row.provenance, row.provenance_note) == ("synthetic", NOTE)


def test_unknown_campaigns(spark):
    campaigns = spark.createDataFrame([("CMP19_01",)], "campaign_id STRING")
    links = spark.createDataFrame([("CMP19_01",), ("CMP19_99",)], "campaign_id STRING")
    assert [r.campaign_id for r in transforms.unknown_campaigns(links, campaigns).collect()] == ["CMP19_99"]
