"""Story 5.1 non-Spark tests: contracts, graph, glossary linkage, DQ rules file."""

from pathlib import Path

import yaml

from fabric_control import load_registry
from fabric_control.contracts import columns, load_schema
from fabric_control.glossary import labelled_terms
from pipelines.dags.job_graph import job_graph

ROOT = Path(__file__).resolve().parents[2]
DATASET = "mart_customer.rfm"


def test_mart_rfm_registered_as_serving_dataset():
    entry = load_registry()[DATASET]
    assert entry["om_fqn"] == "serving.serving.mart_customer.rfm"
    assert entry["openlineage"]["name"] == "serving.mart_customer.rfm"
    assert entry["job_id"] == "marts/customer/rfm"
    assert entry["grain"] == ["customer_id"]


def test_mart_rfm_schema_contract():
    contract = load_schema(DATASET)
    names = [name for name, _ in columns(contract)]
    assert contract["grain"] == ["customer_id"]
    assert names[-3:] == ["_refreshed_at", "_run_id", "_source_version"]
    assert "provenance" in names
    assert "segment" in names and "categories" in names


def test_mart_rfm_yml_matches_contract():
    data = yaml.safe_load((ROOT / "pipelines" / "jobs" / "marts" / "customer" / "rfm" / "mart.yml").read_text())
    contract = load_schema(DATASET)
    assert data["table"] == DATASET
    assert data["grain"] == contract["grain"]
    assert data["modes"] == ["full"]
    assert set(data["metrics"]) <= {name for name, _ in columns(contract)}


def test_mart_rfm_migration_matches_contract():
    sql = (ROOT / "migrations" / "mart_customer" / "202_p3_rfm.sql").read_text()
    contract = load_schema(DATASET)
    assert sql.startswith("-- depends: 000_create_schemas")
    body = sql[sql.index("(") + 1 : sql.index("\n);")]
    names = [line.split()[0] for line in body.splitlines() if line.strip()]
    names = [n for n in names if n.upper() != "PRIMARY"]
    assert names == [name for name, _ in columns(contract)]
    assert "PRIMARY KEY (customer_id)" in sql
    assert f"CREATE TABLE {DATASET} (" in sql
    rollback = (ROOT / "migrations" / "mart_customer" / "202_p3_rfm.rollback.sql").read_text()
    assert rollback.strip() == f"DROP TABLE {DATASET};"


def test_mart_rfm_runs_after_unified_inputs():
    assert job_graph(ROOT)["marts/customer/rfm"] == {"unified/orders", "unified/customers", "unified/order_lines"}


def test_segments_migration_creates_tagged_table():
    sql = (ROOT / "migrations" / "app" / "202_p3_segments.sql").read_text()
    assert sql.startswith("-- depends: 000_create_schemas")
    assert "CREATE TABLE" in sql and "app.segments" in sql
    assert "PRIMARY KEY (audience_id)" in sql
    rollback = (ROOT / "migrations" / "app" / "202_p3_segments.rollback.sql").read_text()
    assert rollback.strip() == "DROP TABLE app.segments;"


def test_score_terms_link_mart_columns():
    terms = labelled_terms()
    assert terms["recency_score"]["dataset_id"] == DATASET
    assert terms["frequency_score"]["column"] == "frequency_score"
    assert terms["monetary_score"]["column"] == "monetary_score"
    assert terms["rfm_segment"]["column"] == "segment"
    assert all(t["provenance"] == "original" for t in terms.values() if t["dataset_id"] == DATASET)


def test_rfm_dq_rules_cover_key_and_scores():
    rules = yaml.safe_load(
        (ROOT / "pipelines" / "jobs" / "marts" / "customer" / "rfm" / "data_quality" / "rfm.yml").read_text()
    )["rules"]
    by_id = {r["rule_id"]: r for r in rules}
    assert by_id["customer_id_unique"]["severity"] == "critical"
    assert {by_id[k]["kwargs"]["column"] for k in by_id if k.endswith("_in_range")} == {
        "recency_score",
        "frequency_score",
        "monetary_score",
    }
