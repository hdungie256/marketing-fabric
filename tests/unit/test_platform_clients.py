import pytest
import yaml

import fabric_control as fc
from fabric_control.clients import airflow, openmetadata
from fabric_control.clients.http import HttpError
from fabric_control.models import DataQualityResult, RuleResult


def entry(dataset_id: str, om_fqn: str) -> dict:
    return {"dataset_id": dataset_id, "om_fqn": om_fqn, "openlineage": {}, "job_id": "x", "tags": []}


@pytest.fixture
def online(monkeypatch, tmp_path):
    (tmp_path / "datasets").mkdir()
    datasets = [entry("raw/a/b", "lake_raw.default.lake.b"), entry("unified/c", "lake_unified.default.lake.c")]
    (tmp_path / "datasets" / "platform.yml").write_text(yaml.safe_dump({"datasets": datasets}))
    monkeypatch.setenv("FABRIC_CONTRACTS_DIR", str(tmp_path))
    monkeypatch.setenv("FABRIC_CONTROL_MODE", "online")


def test_emit_lineage_links_registry_fqns(online, monkeypatch):
    edges = []
    monkeypatch.setattr(openmetadata, "put_pipeline", lambda name: f"pipeline:{name}")
    monkeypatch.setattr(openmetadata, "table_id", lambda fqn: f"id:{fqn}")
    monkeypatch.setattr(openmetadata, "add_lineage", lambda *edge: edges.append(edge))
    fc.emit_lineage("unified/c", ["raw/a/b"], ["unified/c"])
    assert edges == [("id:lake_raw.default.lake.b", "id:lake_unified.default.lake.c", "pipeline:unified/c")]


def test_emit_lineage_does_not_fail_job_when_table_missing(online, monkeypatch):
    def missing(fqn):
        raise HttpError("GET", fqn, 404, "not found")

    monkeypatch.setattr(openmetadata, "put_pipeline", lambda name: "p")
    monkeypatch.setattr(openmetadata, "table_id", missing)
    fc.emit_lineage("unified/c", ["raw/a/b"], ["unified/c"])


def test_emit_lineage_rejects_unregistered_dataset(online):
    with pytest.raises(KeyError):
        fc.emit_lineage("unified/c", ["raw/unknown"], ["unified/c"])


def test_report_data_quality_pushes_each_rule(online, monkeypatch):
    results = []
    monkeypatch.setattr(openmetadata, "put_test_case", lambda fqn, rule_id, description: f"{fqn}.{rule_id}")
    monkeypatch.setattr(openmetadata, "add_test_result", lambda fqn, passed, text: results.append((fqn, passed)))
    rules = [RuleResult("not_null", "critical", True), RuleResult("in_range", "warning", False)]
    fc.report_data_quality(DataQualityResult("raw/a/b", {"mode": "full"}, rules))
    assert results == [("lake_raw.default.lake.b.not_null", True), ("lake_raw.default.lake.b.in_range", False)]


def test_report_data_quality_does_not_fail_job_when_openmetadata_down(online, monkeypatch):
    def down(*args):
        raise ConnectionRefusedError("down")

    monkeypatch.setattr(openmetadata, "put_test_case", down)
    fc.report_data_quality(DataQualityResult("raw/a/b", {"mode": "full"}, [RuleResult("r", "critical", True)]))


def test_trigger_online_calls_airflow(online, monkeypatch):
    monkeypatch.setattr(airflow, "trigger_dag", lambda dag_id, conf: f"run:{dag_id}:{conf['k']}")
    assert fc.trigger("partial_refresh", {"k": 1}) == "run:partial_refresh:1"


def test_offline_functions_do_not_call_services(monkeypatch):
    def fail(*args):
        raise AssertionError("service called in offline mode")

    for name in ("put_pipeline", "table_id", "put_test_case"):
        monkeypatch.setattr(openmetadata, name, fail)
    monkeypatch.setattr(airflow, "trigger_dag", fail)
    fc.emit_lineage("j", ["raw/unknown"], [])
    fc.report_data_quality(DataQualityResult("raw/unknown", {"mode": "full"}, []))
    assert fc.trigger("d", {}) == "offline"
