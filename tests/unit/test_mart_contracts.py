import re
from pathlib import Path

import pytest
import yaml

from fabric_control.contracts import columns, load_schema

ROOT = Path(__file__).resolve().parents[2]
MART_DIR = ROOT / "pipelines" / "jobs" / "marts" / "shared" / "campaign_attributed_daily"
MIGRATIONS = ROOT / "migrations" / "mart_shared"
METADATA = ["_refreshed_at", "_run_id", "_source_version"]

MART_P2 = {
    "mart_shared.campaign_attributed_orders": ("mart_orders.yml", "101_p2_campaign_attributed_orders"),
    "mart_shared.campaign_attributed_daily": ("mart.yml", "102_p2_campaign_attributed_daily"),
}


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


@pytest.mark.parametrize("dataset_id", MART_P2)
def test_mart_contract_has_grain_and_metadata(dataset_id):
    contract = load_schema(dataset_id)
    names = [name for name, _ in columns(contract)]
    assert contract["grain"] and set(contract["grain"]) <= set(names)
    assert names[-3:] == METADATA
    assert "provenance" in names


@pytest.mark.parametrize("dataset_id", MART_P2)
def test_mart_yml_matches_contract(dataset_id):
    mart_yml, _ = MART_P2[dataset_id]
    data = yaml.safe_load((MART_DIR / mart_yml).read_text())
    contract = load_schema(dataset_id)
    assert data["table"] == dataset_id
    assert data["grain"] == contract["grain"]
    assert data["modes"] == ["full"]
    assert set(data["metrics"]) <= {name for name, _ in columns(contract)}


@pytest.mark.parametrize("dataset_id", MART_P2)
def test_migration_matches_contract(dataset_id):
    _, migration_id = MART_P2[dataset_id]
    sql = (MIGRATIONS / f"{migration_id}.sql").read_text()
    contract = load_schema(dataset_id)
    assert sql.startswith("-- depends: 000_create_schemas")
    assert migration_columns(sql) == [name for name, _ in columns(contract)]
    assert re.search(rf"PRIMARY KEY \({', '.join(contract['grain'])}\)", sql)
    assert f"CREATE TABLE {dataset_id} (" in sql
    rollback = (MIGRATIONS / f"{migration_id}.rollback.sql").read_text()
    assert rollback.strip() == f"DROP TABLE {dataset_id};"


def test_order_table_has_period_index():
    sql = (MIGRATIONS / "101_p2_campaign_attributed_orders.sql").read_text()
    assert "ON mart_shared.campaign_attributed_orders (campaign_id, date)" in sql
