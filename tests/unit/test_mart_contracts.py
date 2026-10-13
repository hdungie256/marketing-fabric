import re
from pathlib import Path

import pytest
import yaml

from fabric_control.contracts import columns, load_schema

ROOT = Path(__file__).resolve().parents[2]
JOBS = ROOT / "pipelines" / "jobs" / "marts"
MIGRATIONS = ROOT / "migrations"
METADATA = ["_refreshed_at", "_run_id", "_source_version"]

MARTS = {
    "mart_shared.campaign_attributed_orders": (
        "shared/campaign_attributed_daily/mart_orders.yml",
        "mart_shared/101_p2_campaign_attributed_orders",
    ),
    "mart_shared.campaign_attributed_daily": (
        "shared/campaign_attributed_daily/mart.yml",
        "mart_shared/102_p2_campaign_attributed_daily",
    ),
    "mart_campaign.campaign_overview": (
        "campaign/campaign_overview/mart.yml",
        "mart_campaign/103_p2_campaign_overview",
    ),
}
MART_P2 = {k: v for k, v in MARTS.items() if k.startswith("mart_shared.")}


def mart_files() -> dict[str, dict]:
    marts = {}
    for path in (ROOT / "pipelines" / "jobs" / "marts").rglob("mart*.yml"):
        data = yaml.safe_load(path.read_text())
        marts[data["table"]] = data
    return marts


def migration_columns(sql: str) -> list[str]:
    table = sql[sql.index("CREATE TABLE") :]
    body = table[table.index("(") + 1 : table.index("\n);")]
    names = [line.split()[0] for line in body.splitlines() if line.strip()]
    return [n for n in names if n.upper() != "PRIMARY"]


@pytest.mark.parametrize("dataset_id", MARTS)
def test_mart_contract_has_grain_and_metadata(dataset_id):
    contract = load_schema(dataset_id)
    names = [name for name, _ in columns(contract)]
    assert contract["grain"] and set(contract["grain"]) <= set(names)
    assert names[-3:] == METADATA
    assert "provenance" in names


@pytest.mark.parametrize("dataset_id", MARTS)
def test_mart_yml_matches_contract(dataset_id):
    mart_yml, _ = MARTS[dataset_id]
    data = yaml.safe_load((JOBS / mart_yml).read_text())
    contract = load_schema(dataset_id)
    assert data["table"] == dataset_id
    assert data["grain"] == contract["grain"]
    assert data["modes"] == ["full"]
    assert set(data["metrics"]) <= {name for name, _ in columns(contract)}


@pytest.mark.parametrize("dataset_id", MARTS)
def test_migration_matches_contract(dataset_id):
    _, migration_id = MARTS[dataset_id]
    sql = (MIGRATIONS / f"{migration_id}.sql").read_text()
    contract = load_schema(dataset_id)
    assert sql.startswith("-- depends: 000_create_schemas")
    assert migration_columns(sql) == [name for name, _ in columns(contract)]
    assert re.search(rf"PRIMARY KEY \({', '.join(contract['grain'])}\)", sql)
    assert f"CREATE TABLE {dataset_id} (" in sql
    rollback = (MIGRATIONS / f"{migration_id}.rollback.sql").read_text()
    assert rollback.strip() == f"DROP TABLE {dataset_id};"


def test_order_table_has_period_index():
    sql = (MIGRATIONS / "mart_shared" / "101_p2_campaign_attributed_orders.sql").read_text()
    assert "ON mart_shared.campaign_attributed_orders (campaign_id, date)" in sql


from fabric_control import load_registry  # noqa: E402
from pipelines.dags.job_graph import job_graph  # noqa: E402


def test_registry_mart_datasets_have_contract_and_mart_yml():
    marts = mart_files()
    mart_ids = [d for d in load_registry() if d.startswith("mart_")]
    assert set(MARTS) <= set(mart_ids)
    for dataset_id in mart_ids:
        contract = load_schema(dataset_id)
        assert contract.get("grain"), dataset_id
        assert marts[dataset_id]["grain"] == contract["grain"], dataset_id


def test_mart_registry_entries():
    registry = load_registry()
    for dataset_id in MART_P2:
        entry = registry[dataset_id]
        assert entry["job_id"] == "marts/shared/campaign_attributed_daily"
        assert entry["om_fqn"] == f"serving.serving.{dataset_id}"
        assert entry["openlineage"]["name"] == f"serving.{dataset_id}"


def test_campaign_mart_runs_after_unified():
    graph = job_graph(ROOT)
    assert graph["marts/shared/campaign_attributed_daily"] == {
        "unified/attribution",
        "unified/orders",
        "unified/customers",
    }


def test_shared_metrics_lists_order_table_with_contract_grain():
    entries = {
        e["dataset_id"]: e
        for e in yaml.safe_load((ROOT / "contracts" / "shared_metrics.yml").read_text())["shared_metrics"]
    }
    for dataset_id in MART_P2:
        assert entries[dataset_id]["grain"] == load_schema(dataset_id)["grain"], dataset_id


def test_campaign_overview_registry_and_graph():
    entry = load_registry()["mart_campaign.campaign_overview"]
    assert entry["job_id"] == "marts/campaign/campaign_overview"
    assert entry["om_fqn"] == "serving.serving.mart_campaign.campaign_overview"
    assert job_graph(ROOT)["marts/campaign/campaign_overview"] == {
        "marts/shared/campaign_attributed_daily",
        "unified/campaigns",
    }
