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


import fabric_control as fc  # noqa: E402
from pipelines import io  # noqa: E402
from pipelines.jobs.unified.campaigns import job  # noqa: E402


@pytest.fixture
def lake(monkeypatch, spark):
    tables = {
        "raw/campaign/campaigns": frame(spark, "raw/campaign/campaigns", [campaign("CMP19_01", "Notebooks")]),
        "unified/ref_category_map": category_map(spark),
    }
    written, lineage = {}, []
    monkeypatch.setattr(io, "read_raw", lambda d: tables[d])
    monkeypatch.setattr(io, "read_delta", lambda d, version=None: tables[d])
    monkeypatch.setattr(io, "write_delta", lambda d, df, run_id, replace_where=None: written.update({d: df.collect()}))
    monkeypatch.setattr(fc, "emit_lineage", lambda *args: lineage.append(args))
    return written, lineage


def test_job_writes_and_emits_lineage(lake):
    written, lineage = lake
    job.main({"mode": "full"})
    assert [r.target_category for r in written["unified/campaigns"]] == ["Notebooks & Journals"]
    assert lineage == [(job.JOB_ID, job.INPUTS, job.OUTPUTS)]


def test_job_rejects_scoped_refresh(lake):
    with pytest.raises(ValueError, match="full refresh only"):
        job.main({"mode": "scope", "keys": {"campaign_id": ["CMP19_01"]}})


@pytest.mark.parametrize(
    "path,rule_ids",
    [
        (
            "pipelines/jobs/unified/campaigns/data_quality/campaigns.yml",
            {
                "campaign_id_not_null",
                "campaign_id_unique",
                "provenance_not_null",
                "end_date_not_before_start_date",
                "budget_not_negative",
            },
        ),
        (
            "pipelines/jobs/unified/campaign_targets/data_quality/campaign_targets.yml",
            {
                "campaign_id_not_null",
                "campaign_id_unique",
                "provenance_not_null",
                "evaluation_through_not_before_from",
            },
        ),
    ],
)
def test_dq_files_parse(path, rule_ids):
    import pathlib

    import yaml

    rules = yaml.safe_load(pathlib.Path(path).read_text())["rules"]
    assert {r["rule_id"] for r in rules} == rule_ids
