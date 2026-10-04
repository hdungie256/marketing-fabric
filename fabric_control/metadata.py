from typing import Any

from fabric_control.clients import openmetadata
from fabric_control.clients.http import HttpError
from fabric_control.config import log, mode, stub
from fabric_control.contracts import columns, load_schema
from fabric_control.models import Status
from fabric_control.registry import load_registry


def sync_glossary() -> None:
    stub("sync_glossary")


def sync_tags() -> None:
    stub("sync_tags")


def emit_lineage(job_id: str, inputs: list[str], outputs: list[str]) -> None:
    if mode() == "offline":
        stub("emit_lineage", job_id=job_id, inputs=inputs, outputs=outputs)
        return
    registry = load_registry()
    fqns = {dataset_id: registry[dataset_id]["om_fqn"] for dataset_id in [*inputs, *outputs]}
    try:
        pipeline_id = openmetadata.put_pipeline(job_id)
        ids = {dataset_id: openmetadata.table_id(fqn) for dataset_id, fqn in fqns.items()}
        for source in inputs:
            for target in outputs:
                openmetadata.add_lineage(ids[source], ids[target], pipeline_id)
    except (HttpError, OSError) as e:
        log.warning("lineage for %s not recorded: %s", job_id, e)


RAW_COLUMNS = [
    ("_load_id", "string"),
    ("_ingested_at", "timestamp"),
    ("_source", "string"),
    ("_load_kind", "string"),
    ("_source_version", "bigint"),
    ("_schema_version", "string"),
    ("_run_id", "string"),
]
DELTA_COLUMNS = [("_run_id", "string")]


def delta_columns(dataset_id: str) -> list[tuple[str, str]]:
    extra = RAW_COLUMNS if dataset_id.startswith("raw/") else DELTA_COLUMNS
    return columns(load_schema(dataset_id)) + extra


def register(dataset_id: str) -> None:
    if mode() == "offline":
        stub("register", dataset_id=dataset_id)
        return
    openmetadata.put_table(load_registry()[dataset_id]["om_fqn"], delta_columns(dataset_id))


def register_all() -> list[str]:
    datasets = [d for d, entry in load_registry().items() if entry["om_fqn"].startswith("lake_")]
    for dataset_id in datasets:
        register(dataset_id)
    return datasets


def catalog(filter: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    return stub("catalog", [], filter=filter)


def search(q: str) -> list[dict[str, Any]]:
    return stub("search", [], q=q)


def term(term_id: str) -> dict[str, Any] | None:
    return stub("term", None, term_id=term_id)


def lineage(dataset_id: str, depth: int = 1) -> dict[str, list]:
    return stub("lineage", {"nodes": [], "edges": []}, dataset_id=dataset_id, depth=depth)


def latest_score(dataset_id: str) -> tuple[float, Status] | None:
    return stub("latest_score", None, dataset_id=dataset_id)


def effective_matrix() -> list[dict[str, Any]]:
    return stub("effective_matrix", [])
