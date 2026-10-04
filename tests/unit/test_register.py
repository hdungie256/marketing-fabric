import pytest
import yaml

import fabric_control as fc
from fabric_control.clients import openmetadata
from fabric_control.metadata import RAW_COLUMNS


@pytest.fixture
def contracts(monkeypatch, tmp_path):
    datasets = [
        {"dataset_id": "raw/a/b", "om_fqn": "lake_raw.default.lake.b", "natural_key": ["id"]},
        {"dataset_id": "unified/c", "om_fqn": "lake_unified.default.lake.c"},
        {"dataset_id": "mart_shared.d", "om_fqn": "serving.serving.mart_shared.d"},
    ]
    for entry in datasets:
        entry.update({"openlineage": {}, "job_id": "x", "tags": []})
        path = tmp_path / "schemas" / f"{entry['dataset_id']}.yml"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(yaml.safe_dump({"schema_version": "1.0.0", "columns": [{"name": "id", "type": "bigint"}]}))
    (tmp_path / "datasets").mkdir()
    (tmp_path / "datasets" / "all.yml").write_text(yaml.safe_dump({"datasets": datasets}))
    monkeypatch.setenv("FABRIC_CONTRACTS_DIR", str(tmp_path))
    monkeypatch.setenv("FABRIC_CONTROL_MODE", "online")
    tables = {}
    monkeypatch.setattr(openmetadata, "put_table", lambda fqn, columns: tables.setdefault(fqn, columns))
    return tables


def test_column_types():
    assert openmetadata.column("amount", "decimal(18,2)") == {
        "name": "amount",
        "dataType": "DECIMAL",
        "precision": 18,
        "scale": 2,
        "dataTypeDisplay": "decimal(18,2)",
    }
    assert openmetadata.column("id", "bigint")["dataType"] == "BIGINT"
    with pytest.raises(KeyError):
        openmetadata.column("x", "map<string,int>")


def test_put_table_creates_parents(monkeypatch):
    calls = []
    monkeypatch.setattr(
        openmetadata, "call", lambda method, path, body=None: calls.append((path, body)) or {"id": "t1"}
    )
    assert openmetadata.put_table("lake_raw.default.lake.orders", [("id", "bigint")]) == "t1"
    assert [p for p, _ in calls] == ["databases", "databaseSchemas", "tables"]
    assert calls[1][1] == {"name": "lake", "database": "lake_raw.default"}
    assert calls[2][1]["databaseSchema"] == "lake_raw.default.lake"


def test_register_raw_adds_load_columns(contracts):
    fc.register("raw/a/b")
    assert contracts["lake_raw.default.lake.b"] == [("id", "bigint"), *RAW_COLUMNS]


def test_register_unified_adds_run_id(contracts):
    fc.register("unified/c")
    assert contracts["lake_unified.default.lake.c"] == [("id", "bigint"), ("_run_id", "string")]


def test_register_all_only_lake_datasets(contracts):
    assert sorted(fc.register_all()) == ["raw/a/b", "unified/c"]
    assert "serving.serving.mart_shared.d" not in contracts


def test_register_offline_is_noop(monkeypatch):
    monkeypatch.setattr(openmetadata, "put_table", lambda *a: pytest.fail("called offline"))
    fc.register("raw/unknown")
