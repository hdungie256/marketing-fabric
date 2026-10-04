from pathlib import Path
from typing import Any

import yaml

from fabric_control.config import contracts_dir


class ContractError(Exception):
    pass


def load_schema(dataset_id: str, directory: Path | None = None) -> dict[str, Any]:
    path = (directory or contracts_dir() / "schemas") / f"{dataset_id}.yml"
    if not path.exists():
        raise ContractError(f"no schema contract for {dataset_id} at {path}")
    contract = yaml.safe_load(path.read_text()) or {}
    if not contract.get("schema_version") or not contract.get("columns"):
        raise ContractError(f"{path}: schema_version and columns are required")
    for column in contract["columns"]:
        if not column.get("name") or not column.get("type"):
            raise ContractError(f"{path}: every column needs name and type")
    return contract


def columns(contract: dict[str, Any]) -> list[tuple[str, str]]:
    return [(c["name"], c["type"]) for c in contract["columns"]]
