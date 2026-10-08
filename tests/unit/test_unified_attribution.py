from datetime import date

import pytest

from pipelines.jobs.unified.attribution import transforms
from tests.unit.unified_fixtures import category_map, contract, frame, schema

pytest.importorskip("pyspark.sql")

NOTE = "SYNTHETIC; no ad exposure evidence"


def link(customer_id, transaction_id, campaign_id="CMP19_01", category="Apparel", day=date(2019, 1, 16)):
    return (
        f"C{customer_id}_T{transaction_id}",
        customer_id,
        transaction_id,
        day,
        campaign_id,
        category,
        "TARGET_CATEGORY_PURCHASE_SAMPLE",
        "synthetic",
        NOTE,
    )


def unified(spark, rows):
    return transforms.transform(frame(spark, "raw/campaign/attribution", rows), category_map(spark))


def orders(spark, *keys):
    return spark.createDataFrame([(k,) for k in keys], "order_key STRING")


def test_transform_matches_contract(spark):
    assert schema(unified(spark, [link(14142, 17936)])) == contract("unified/attribution")


def test_order_key_follows_r1(spark):
    row = unified(spark, [link(14142, 17936)]).collect()[0]
    assert (row.order_key, row.canonical_order_id, row.transaction_id) == ("14142|17936", "C14142_T17936", 17936)


def test_order_date_and_provenance(spark):
    row = unified(spark, [link(14142, 17936)]).collect()[0]
    assert (row.order_date, row.provenance, row.provenance_note) == (date(2019, 1, 16), "synthetic", NOTE)


def test_matched_category_is_normalized(spark):
    row = unified(spark, [link(1, 2, category="Notebooks")]).collect()[0]
    assert (row.matched_category, row.source_matched_category) == ("Notebooks & Journals", "Notebooks")


def test_no_orphans_when_every_order_exists(spark):
    df = unified(spark, [link(14142, 17936), link(13065, 17950)])
    assert transforms.orphan_links(df, orders(spark, "14142|17936", "13065|17950")).count() == 0


def test_missing_order_is_an_orphan(spark):
    df = unified(spark, [link(14142, 17936), link(13065, 17950)])
    assert [r.order_key for r in transforms.orphan_links(df, orders(spark, "14142|17936")).collect()] == ["13065|17950"]


def test_shared_transaction_id_is_checked_per_customer(spark):
    df = unified(spark, [link(13065, 17951), link(14606, 17951)])
    assert {r.order_key for r in df.collect()} == {"13065|17951", "14606|17951"}
    assert [r.order_key for r in transforms.orphan_links(df, orders(spark, "13065|17951")).collect()] == ["14606|17951"]


def test_outside_campaign_window(spark):
    campaigns = spark.createDataFrame(
        [("CMP19_01", date(2019, 1, 15), date(2019, 2, 10))], "campaign_id STRING, start_date DATE, end_date DATE"
    )
    df = unified(spark, [link(1, 1, day=date(2019, 1, 15)), link(2, 2, day=date(2019, 3, 1))])
    assert [r.order_key for r in transforms.outside_campaign_window(df, campaigns).collect()] == ["2|2"]


import fabric_control as fc  # noqa: E402
from fabric_control.models import GateFailed  # noqa: E402
from pipelines import io  # noqa: E402
from pipelines.jobs.unified.attribution import job  # noqa: E402


def lake(monkeypatch, spark, order_keys, baseline=2):
    tables = {
        "raw/campaign/attribution": frame(spark, "raw/campaign/attribution", [link(14142, 17936), link(13065, 17950)]),
        "unified/ref_category_map": category_map(spark),
        "unified/orders": orders(spark, *order_keys),
        "unified/campaigns": spark.createDataFrame(
            [("CMP19_01", date(2019, 1, 15), date(2019, 2, 10))], "campaign_id STRING, start_date DATE, end_date DATE"
        ),
    }
    written, lineage = {}, []
    monkeypatch.setattr(io, "read_raw", lambda d: tables[d])
    monkeypatch.setattr(io, "read_delta", lambda d, version=None: tables[d])
    monkeypatch.setattr(io, "write_delta", lambda d, df, run_id, replace_where=None: written.update({d: df.collect()}))
    monkeypatch.setattr(fc, "emit_lineage", lambda *args: lineage.append(args))
    monkeypatch.setattr(job, "load_baselines", lambda: {"raw/campaign/attribution": baseline})
    return written, lineage


def test_job_writes_when_every_order_exists(monkeypatch, spark):
    written, lineage = lake(monkeypatch, spark, ["14142|17936", "13065|17950"])
    job.main({"mode": "full"})
    assert {r.order_key for r in written["unified/attribution"]} == {"14142|17936", "13065|17950"}
    assert lineage == [(job.JOB_ID, job.INPUTS, job.OUTPUTS)]


def test_job_gates_orphan_links(monkeypatch, spark):
    written, _ = lake(monkeypatch, spark, ["14142|17936"])
    with pytest.raises(GateFailed, match="order_key_in_orders"):
        job.main({"mode": "full"})
    assert written == {}


def test_job_gates_row_count_off_baseline(monkeypatch, spark):
    written, _ = lake(monkeypatch, spark, ["14142|17936", "13065|17950"], baseline=1290)
    with pytest.raises(GateFailed, match="row_count_baseline"):
        job.main({"mode": "full"})
    assert written == {}


def test_missing_baseline_fails_closed(spark):
    df = unified(spark, [link(1, 1)])
    campaigns = spark.createDataFrame(
        [("CMP19_01", date(2019, 1, 1), date(2019, 12, 31))], "campaign_id STRING, start_date DATE, end_date DATE"
    )
    rules = {r.rule_id: r.passed for r in job.cross_rules(df, orders(spark, "1|1"), campaigns, None)}
    assert rules == {
        "order_key_in_orders": True,
        "campaign_id_in_campaigns": True,
        "row_count_baseline": False,
        "order_date_in_campaign_window": True,
    }


@pytest.mark.parametrize(
    ("path", "rule_ids"),
    [
        (
            "pipelines/jobs/unified/attribution/data_quality/attribution.yml",
            {"order_key_not_null", "order_key_unique", "campaign_id_not_null", "provenance_not_null"},
        ),
    ],
)
def test_dq_files_parse(path, rule_ids):
    import pathlib

    import yaml

    rules = yaml.safe_load(pathlib.Path(path).read_text())["rules"]
    assert {r["rule_id"] for r in rules} == rule_ids
