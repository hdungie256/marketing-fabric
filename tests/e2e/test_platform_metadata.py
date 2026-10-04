import pytest
from pyspark.sql import functions as F

import fabric_control as fc
from fabric_control.bootstrap import delta_service
from fabric_control.clients import openmetadata
from fabric_control.models import DataQualityResult, RuleResult
from pipelines.io import write_delta
from pipelines.io.spark import get_spark
from pipelines.io.storage import ensure_bucket

SOURCE = "raw/_e2e/lineage_source"
TARGET = "raw/_e2e/lineage_target"
FQNS = {SOURCE: "lake_e2e.default.lake.lineage_source", TARGET: "lake_e2e.default.lake.lineage_target"}
COLUMNS = [("order_id", "bigint"), ("v", "int")]


@pytest.fixture
def tables(registry):
    ensure_bucket()
    openmetadata.put_database_service(*delta_service("e2e"))
    registry(FQNS, {d: COLUMNS for d in FQNS})
    spark = get_spark("e2e_metadata")
    for dataset_id in FQNS:
        write_delta(dataset_id, spark.range(2).withColumnRenamed("id", "order_id").withColumn("v", F.lit(1)), "e2e")
        fc.register(dataset_id)


def test_bot_token_authenticates():
    assert openmetadata.call("GET", "users/loggedInUser")["name"] == openmetadata.BOT


def test_register_creates_table_with_contract_columns(tables):
    table = openmetadata.call("GET", f"tables/name/{openmetadata.quote(FQNS[SOURCE])}?fields=columns")
    names = [c["name"] for c in table["columns"]]
    assert names[:2] == ["order_id", "v"] and "_load_id" in names


def test_emit_lineage(tables):
    fc.emit_lineage("e2e/lineage", [SOURCE], [TARGET])
    path = f"lineage/table/name/{openmetadata.quote(FQNS[TARGET])}?upstreamDepth=1&downstreamDepth=0"
    graph = openmetadata.call("GET", path)
    names = {node["id"]: node["fullyQualifiedName"] for node in graph["nodes"]}
    edges = {
        (names.get(e["fromEntity"]), (e.get("lineageDetails") or {}).get("pipeline", {}).get("fullyQualifiedName"))
        for e in graph["upstreamEdges"]
    }
    assert (FQNS[SOURCE], "fabric.e2e/lineage") in edges


def test_report_data_quality(tables):
    result = DataQualityResult(SOURCE, {"mode": "full"}, [RuleResult("e2e_rule", "critical", False)])
    fc.report_data_quality(result)
    fqn = openmetadata.quote(FQNS[SOURCE] + ".e2e_rule")
    case = openmetadata.call("GET", f"dataQuality/testCases/name/{fqn}?fields=testCaseResult")
    assert case["testCaseResult"]["testCaseStatus"] == "Failed"
