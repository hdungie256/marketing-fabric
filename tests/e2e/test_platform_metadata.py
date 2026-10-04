import pytest
from pyspark.sql import functions as F

import fabric_control as fc
from fabric_control.clients import openmetadata
from fabric_control.models import DataQualityResult, RuleResult
from pipelines.io import write_delta
from pipelines.io.spark import get_spark
from pipelines.io.storage import ensure_bucket

SOURCE = "raw/_e2e/lineage_source"
TARGET = "raw/_e2e/lineage_target"
FQNS = {SOURCE: "lake_raw.default.lake.lineage_source", TARGET: "lake_raw.default.lake.lineage_target"}


@pytest.fixture(scope="module")
def tables():
    ensure_bucket()
    spark = get_spark("e2e_metadata")
    for dataset_id in FQNS:
        write_delta(dataset_id, spark.range(2).withColumn("v", F.lit(1)), "e2e")
    assert openmetadata.ingest("lake_raw") == "success"


def test_bot_token_authenticates():
    assert openmetadata.call("GET", "users/loggedInUser")["name"] == openmetadata.BOT


def test_emit_lineage(tables, registry):
    registry(FQNS)
    fc.emit_lineage("e2e/lineage", [SOURCE], [TARGET])
    path = f"lineage/table/name/{openmetadata.quote(FQNS[TARGET])}?upstreamDepth=1&downstreamDepth=0"
    graph = openmetadata.call("GET", path)
    names = {node["id"]: node["fullyQualifiedName"] for node in graph["nodes"]}
    edges = {
        (names.get(e["fromEntity"]), (e.get("lineageDetails") or {}).get("pipeline", {}).get("fullyQualifiedName"))
        for e in graph["upstreamEdges"]
    }
    assert (FQNS[SOURCE], "fabric.e2e/lineage") in edges


def test_report_data_quality(tables, registry):
    registry(FQNS)
    result = DataQualityResult(SOURCE, {"mode": "full"}, [RuleResult("e2e_rule", "critical", False)])
    fc.report_data_quality(result)
    case = openmetadata.call(
        "GET", f"dataQuality/testCases/name/{openmetadata.quote(FQNS[SOURCE] + '.e2e_rule')}?fields=testCaseResult"
    )
    assert case["testCaseResult"]["testCaseStatus"] == "Failed"
