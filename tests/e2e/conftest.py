import os

import psycopg
import pytest
import yaml

collect_ignore_glob = [] if os.environ.get("FABRIC_E2E") == "1" else ["test_*.py"]

E2E_RUNS = "SELECT run_id FROM ops.runs WHERE job_id LIKE 'e2e/%' OR job_id LIKE 'ingest/\\_e2e%'"
PURGE_E2E = [
    f"DELETE FROM ops.alerts WHERE run_id IN ({E2E_RUNS})",
    f"DELETE FROM ops.load_reconciliation WHERE run_id IN ({E2E_RUNS})",
    f"DELETE FROM ops.metric_change_log WHERE run_id IN ({E2E_RUNS})",
    f"DELETE FROM ops.dq_results WHERE run_id IN ({E2E_RUNS}) OR dataset_id LIKE 'raw/\\_e2e/%'",
    f"DELETE FROM ops.runs WHERE run_id IN ({E2E_RUNS})",
]


def purge_e2e() -> None:
    with psycopg.connect(os.environ["SERVING_DB_DSN"]) as conn:
        for statement in PURGE_E2E:
            conn.execute(statement)


@pytest.fixture(scope="session", autouse=True)
def e2e_ops_rows():
    """Drop the ops rows of e2e-only jobs and datasets so no screen shows them after a test session (UX-DR42)."""
    purge_e2e()
    yield
    purge_e2e()


@pytest.fixture(autouse=True)
def offline_mode(monkeypatch):
    monkeypatch.setenv("FABRIC_CONTROL_MODE", "online")


@pytest.fixture
def registry(monkeypatch, tmp_path):
    def write(entries: dict[str, str], schemas: dict[str, list[tuple[str, str]]] | None = None) -> None:
        datasets = [
            {
                "dataset_id": d,
                "om_fqn": fqn,
                "openlineage": {},
                "job_id": "e2e",
                "tags": [],
                "natural_key": ["order_id"],
            }
            for d, fqn in entries.items()
        ]
        (tmp_path / "datasets").mkdir(exist_ok=True)
        (tmp_path / "datasets" / "e2e.yml").write_text(yaml.safe_dump({"datasets": datasets}))
        for dataset_id, cols in (schemas or {}).items():
            path = tmp_path / "schemas" / f"{dataset_id}.yml"
            path.parent.mkdir(parents=True, exist_ok=True)
            contract = {"schema_version": "1.0.0", "columns": [{"name": n, "type": t} for n, t in cols]}
            path.write_text(yaml.safe_dump(contract))
        monkeypatch.setenv("FABRIC_CONTRACTS_DIR", str(tmp_path))

    return write
