import os

import pytest
import yaml

collect_ignore_glob = [] if os.environ.get("FABRIC_E2E") == "1" else ["test_*.py"]


@pytest.fixture(autouse=True)
def offline_mode(monkeypatch):
    monkeypatch.setenv("FABRIC_CONTROL_MODE", "online")


@pytest.fixture
def registry(monkeypatch, tmp_path):
    def write(entries: dict[str, str]) -> None:
        datasets = [
            {"dataset_id": d, "om_fqn": fqn, "openlineage": {}, "job_id": "e2e", "tags": []}
            for d, fqn in entries.items()
        ]
        (tmp_path / "datasets").mkdir(exist_ok=True)
        (tmp_path / "datasets" / "e2e.yml").write_text(yaml.safe_dump({"datasets": datasets}))
        monkeypatch.setenv("FABRIC_CONTRACTS_DIR", str(tmp_path))

    return write
