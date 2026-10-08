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
