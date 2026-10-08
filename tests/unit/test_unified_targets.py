from datetime import date
from decimal import Decimal

import pytest

from pipelines.jobs.unified.campaign_targets import transforms
from tests.unit.unified_fixtures import contract, frame, schema

pytest.importorskip("pyspark.sql")

ROW = (
    "CMP19_02",
    "Attributed order count",
    Decimal("495.00"),
    date(2019, 3, 10),
    date(2019, 4, 5),
    "Retrospective demo target; not a real pre-campaign plan",
    "synthetic",
    "SYNTHETIC",
)


def test_transform_matches_contract(spark):
    raw = frame(spark, "raw/campaign/targets", [ROW])
    assert schema(transforms.transform(raw)) == contract("unified/campaign_targets")


def test_transform_keeps_values_and_provenance(spark):
    row = transforms.transform(frame(spark, "raw/campaign/targets", [ROW])).collect()[0]
    assert (row.target_value, row.provenance, row.provenance_note) == (Decimal("495.00"), "synthetic", "SYNTHETIC")


import fabric_control as fc  # noqa: E402
from fabric_control.models import GateFailed  # noqa: E402
from pipelines import io  # noqa: E402
from pipelines.jobs.unified.campaign_targets import job  # noqa: E402


def lake(monkeypatch, spark, campaign_ids):
    tables = {
        "raw/campaign/targets": frame(spark, "raw/campaign/targets", [ROW]),
        "unified/campaigns": spark.createDataFrame([(c,) for c in campaign_ids], "campaign_id STRING"),
    }
    written = {}
    monkeypatch.setattr(io, "read_raw", lambda d: tables[d])
    monkeypatch.setattr(io, "read_delta", lambda d, version=None: tables[d])
    monkeypatch.setattr(io, "write_delta", lambda d, df, run_id, replace_where=None: written.update({d: df.collect()}))
    monkeypatch.setattr(fc, "emit_lineage", lambda *args: None)
    return written


def test_job_writes_targets_for_known_campaigns(monkeypatch, spark):
    written = lake(monkeypatch, spark, ["CMP19_02"])
    job.main({"mode": "full"})
    assert [r.campaign_id for r in written["unified/campaign_targets"]] == ["CMP19_02"]


def test_job_gates_unknown_campaign(monkeypatch, spark):
    written = lake(monkeypatch, spark, ["CMP19_01"])
    with pytest.raises(GateFailed, match="campaign_id_in_campaigns"):
        job.main({"mode": "full"})
    assert written == {}
