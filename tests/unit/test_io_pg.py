from datetime import UTC, datetime

import pytest

from pipelines import io
from pipelines.io import pg

NOW = datetime(2026, 10, 12, 7, 0, tzinfo=UTC)


def test_stamp_appends_same_metadata_to_every_row():
    rows = pg.stamp([("CMP19_01", 3), ("CMP19_02", 4)], "run-1", {"raw/b": 2, "raw/a": 1}, NOW)
    assert rows == [
        ("CMP19_01", 3, NOW, "run-1", '{"raw/a": 1, "raw/b": 2}'),
        ("CMP19_02", 4, NOW, "run-1", '{"raw/a": 1, "raw/b": 2}'),
    ]


@pytest.mark.parametrize("table", ["ops.runs", "unified/orders", "mart_shared.not_registered"])
def test_write_pg_full_rejects_non_mart_or_unregistered(table):
    with pytest.raises(ValueError, match="registered mart_"):
        io.write_pg_full(table, object(), "run-1", {})


@pytest.mark.parametrize("dataset_id", ["mart_campaign.anything", "ops.runs", "mart_shared.not_registered"])
def test_read_pg_only_reads_registered_shared_marts(dataset_id):
    with pytest.raises(ValueError, match="registered mart_shared"):
        io.read_pg(dataset_id)
