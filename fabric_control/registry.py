from pathlib import Path

import yaml

from fabric_control.config import contracts_dir

REQUIRED_FIELDS = ("dataset_id", "om_fqn", "openlineage", "job_id", "tags")


class RegistryError(Exception):
    pass


def load_registry(directory: Path | None = None) -> dict[str, dict]:
    directory = directory or contracts_dir() / "datasets"
    datasets: dict[str, dict] = {}
    for path in sorted(directory.glob("*.yml")):
        for entry in (yaml.safe_load(path.read_text()) or {}).get("datasets") or []:
            dataset_id = entry.get("dataset_id")
            missing = [f for f in REQUIRED_FIELDS if f not in entry]
            if missing:
                raise RegistryError(f"{path.name}: {dataset_id} missing {missing}")
            if dataset_id in datasets:
                raise RegistryError(f"{path.name}: duplicate dataset_id {dataset_id}")
            datasets[dataset_id] = entry
    return datasets
