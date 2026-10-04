from typing import Any

from fabric_control.clients import openmetadata
from fabric_control.clients.http import HttpError
from fabric_control.config import log, mode, stub
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


def register(dataset_id: str) -> None:
    stub("register", dataset_id=dataset_id)


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
