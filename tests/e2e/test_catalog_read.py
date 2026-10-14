import pytest

import fabric_control as fc
from fabric_control.bootstrap import delta_service
from fabric_control.clients import openmetadata
from fabric_control.models import DataQualityResult, RuleResult

SOURCE = "raw/_e2e/catalog_source"
TARGET = "raw/_e2e/catalog_target"
FQNS = {SOURCE: "lake_e2e.default.lake.catalog_source", TARGET: "lake_e2e.default.lake.catalog_target"}
COLUMNS = [("order_id", "bigint"), ("v", "int")]


@pytest.fixture
def tables(registry):
    openmetadata.put_database_service(*delta_service("e2e"))
    registry(FQNS, {d: COLUMNS for d in FQNS})
    for dataset_id in FQNS:
        fc.register(dataset_id)


def test_lineage_reads_openmetadata_edges(tables):
    fc.emit_lineage("e2e/catalog", [SOURCE], [TARGET])
    graph = fc.lineage(TARGET, depth=1)
    assert {"from": SOURCE, "to": TARGET, "job_id": "e2e/catalog"} in graph["edges"]
    assert {n["dataset_id"] for n in graph["nodes"]} == {SOURCE, TARGET}


def test_latest_score_reads_openmetadata_results(tables):
    rules = [RuleResult("e2e_catalog_critical", "critical", True), RuleResult("e2e_catalog_warning", "warning", False)]
    with fc.run("e2e/catalog", {"mode": "full"}):
        fc.report_data_quality(DataQualityResult(SOURCE, {"mode": "full"}, rules))
    assert fc.latest_score(SOURCE) == (50.0, "Amber")
    assert fc.latest_score(TARGET) == fc.NOT_MEASURED


def test_catalog_has_refresh_time_for_every_loaded_raw_dataset():
    items = fc.catalog({"layer": "raw"})
    assert items and all(i["refreshed_at"] is not None for i in items)
    assert {i["dataset_id"]: i["provenance"] for i in items}["raw/campaign/attribution"] == "synthetic"
