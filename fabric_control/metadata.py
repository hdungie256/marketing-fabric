from typing import Any

from fabric_control.config import stub
from fabric_control.models import Status


def sync_glossary() -> None:
    stub("sync_glossary")


def sync_tags() -> None:
    stub("sync_tags")


def emit_lineage(job_id: str, inputs: list[str], outputs: list[str]) -> None:
    stub("emit_lineage", job_id=job_id, inputs=inputs, outputs=outputs)


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
