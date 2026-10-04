import os

import pytest
import yaml

collect_ignore_glob = [] if os.environ.get("FABRIC_E2E") == "1" else ["test_*.py"]


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
