import ast
from pathlib import Path

import pytest
import yaml

from fabric_control import load_registry
from fabric_control.contracts import ContractError, columns, load_schema
from pipelines.jobs.ingest.reconciliation import compare_schema, schema_drift

ROOT = Path(__file__).resolve().parents[2]
EXPECTED = [("id", "bigint"), ("name", "string"), ("amount", "decimal(18,2)")]


def test_load_schema(tmp_path):
    path = tmp_path / "raw" / "a" / "b.yml"
    path.parent.mkdir(parents=True)
    path.write_text("schema_version: 1.0.0\ncolumns:\n  - {name: id, type: bigint}\n")
    assert columns(load_schema("raw/a/b", tmp_path)) == [("id", "bigint")]
    with pytest.raises(ContractError):
        load_schema("raw/a/missing", tmp_path)


def test_matching_schema_has_no_drift():
    diff = compare_schema(EXPECTED, dict(EXPECTED))
    assert not diff.drift and not diff.extra


def test_untyped_source_checks_names_only():
    assert not compare_schema(EXPECTED, {"id": None, "name": None, "amount": None}).drift


def test_renamed_column_is_drift():
    diff = compare_schema(EXPECTED, {"id": "bigint", "full_name": "string", "amount": "decimal(18,2)"})
    assert diff.missing == ["name"] and diff.extra == ["full_name"] and diff.drift
    check = schema_drift("l1", "raw/a/b", 3, 3, diff)
    assert not check.passed and check.reason.startswith("schema_drift")


def test_retyped_column_is_drift():
    diff = compare_schema(EXPECTED, {"id": "string", "name": "string", "amount": "decimal(18,2)"})
    assert diff.retyped == ["id string != bigint"] and diff.drift


def test_extra_column_is_not_drift():
    diff = compare_schema(EXPECTED, {**dict(EXPECTED), "note": "string"})
    assert diff.extra == ["note"] and not diff.drift


def test_registry_raw_datasets_have_contracts_and_keys():
    for dataset_id, entry in load_registry().items():
        if dataset_id.startswith("raw/"):
            names = [name for name, _ in columns(load_schema(dataset_id))]
            assert set(entry["natural_key"]) <= set(names), dataset_id


def test_every_raw_dataset_has_an_ingest_job():
    outputs = set()
    for path in (ROOT / "pipelines" / "jobs" / "ingest").glob("*/job.py"):
        for node in ast.parse(path.read_text()).body:
            if isinstance(node, ast.Assign) and any(getattr(t, "id", None) == "OUTPUTS" for t in node.targets):
                outputs |= set(ast.literal_eval(node.value))
    assert outputs == {d for d in load_registry() if d.startswith("raw/")}


UNIFIED_P2 = [
    "unified/campaigns",
    "unified/attribution",
    "unified/campaign_targets",
    "unified/coupon_plan",
    "unified/exceptions_coupon_plan_duplicate",
]


@pytest.mark.parametrize("dataset_id", UNIFIED_P2)
def test_unified_contract_declares_grain(dataset_id):
    contract = load_schema(dataset_id)
    names = [name for name, _ in columns(contract)]
    assert contract.get("grain"), dataset_id
    assert set(contract["grain"]) <= set(names), dataset_id
    assert "provenance" in names or dataset_id.startswith("unified/exceptions_")


def test_registry_unified_datasets_have_contracts():
    for dataset_id in load_registry():
        if dataset_id.startswith("unified/"):
            assert columns(load_schema(dataset_id)), dataset_id


def test_exception_classes_include_coupon_plan_duplicate():
    data = yaml.safe_load((ROOT / "contracts" / "exceptions.yml").read_text())
    assert "coupon_plan_duplicate" in data["classes"]
    exception_columns = [(c["name"], c["type"]) for c in data["columns"]]
    assert columns(load_schema("unified/exceptions_coupon_plan_duplicate")) == exception_columns
