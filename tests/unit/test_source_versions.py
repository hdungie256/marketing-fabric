import pytest

from pipelines.dags.job_graph import writers
from pipelines.io.lineage import ROOT, job_inputs, raw_ancestors

WRITERS = {
    "raw/sales/lines": "ingest/sales",
    "raw/crm/customers": "ingest/crm",
    "unified/orders": "unified/orders",
    "unified/customers": "unified/customers",
    "unified/map": "unified/map",
}
INPUTS = {
    "unified/orders": ["raw/sales/lines", "unified/map"],
    "unified/customers": ["raw/crm/customers", "raw/sales/lines"],
    "unified/map": [],
}


def test_walks_unified_to_raw():
    assert raw_ancestors(["unified/orders", "unified/customers"], WRITERS, INPUTS.__getitem__) == [
        "raw/crm/customers",
        "raw/sales/lines",
    ]


def test_raw_input_is_its_own_ancestor():
    assert raw_ancestors(["raw/sales/lines"], WRITERS, INPUTS.__getitem__) == ["raw/sales/lines"]


def test_unregistered_dataset_raises():
    with pytest.raises(ValueError, match="unified/unknown"):
        raw_ancestors(["unified/unknown"], WRITERS, INPUTS.__getitem__)


def test_repo_campaign_mart_ancestors():
    inputs = ["unified/attribution", "unified/orders", "unified/customers"]
    assert raw_ancestors(inputs, writers(ROOT), job_inputs) == [
        "raw/campaign/attribution",
        "raw/campaign/campaigns",
        "raw/crm/customers",
        "raw/sales/sales_lines",
    ]


def raw_frame(spark, *loads):
    """Rows of (load_id, source_version); source_versions() keeps only loads that passed reconciliation."""
    return spark.createDataFrame(list(loads), "_load_id STRING, _source_version BIGINT")


def lake(monkeypatch, tables, passed):
    from pipelines import io

    monkeypatch.setattr(io, "read_delta", lambda d, version=None: tables[d])
    monkeypatch.setattr(io.ops, "passed_loads", lambda d: passed[d])
    monkeypatch.setattr(io.lineage, "raw_ancestors", lambda ids, w, i: sorted(tables))
    return io


def test_source_versions_takes_max_of_passed_loads_per_raw(monkeypatch, spark):
    tables = {
        "raw/campaign/attribution": raw_frame(spark, ("a1", 1), ("a3", 3), ("a9", 9)),
        "raw/campaign/campaigns": raw_frame(spark, ("c2", 2)),
    }
    io = lake(monkeypatch, tables, {"raw/campaign/attribution": ["a1", "a3"], "raw/campaign/campaigns": ["c2"]})
    result = io.source_versions(["unified/attribution"])
    assert result == {"raw/campaign/attribution": 3, "raw/campaign/campaigns": 2}  # a9 failed reconciliation
    assert list(result) == sorted(result)


def test_source_versions_rejects_raw_without_passed_load(monkeypatch, spark):
    io = lake(monkeypatch, {"raw/crm/customers": raw_frame(spark, ("x1", 4))}, {"raw/crm/customers": []})
    with pytest.raises(ValueError, match="raw/crm/customers"):
        io.source_versions(["unified/customers"])
