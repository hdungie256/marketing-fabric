import functools
from typing import Any

from fabric_control.catalog import ancestors, upstream_graph
from fabric_control.clients import postgres
from fabric_control.config import contracts_dir, jobs_dir, log, mode, stub
from fabric_control.models import Event
from fabric_control.registry import load_registry

FRESH = {"stale": False, "since": None, "cause": None, "datasets": []}


def affected_by(event: Event) -> list[dict[str, Any]]:
    return stub("affected_by", [], event=event)


@functools.cache
def lineage_graph(contracts: str, jobs: str) -> dict[str, set[str]]:
    return upstream_graph(load_registry())


def gated_datasets(registry: dict[str, dict]) -> dict[str, Any]:
    gated = {}
    for job_id, since, _, red in postgres.gated_runs():
        outputs = [d for d, entry in registry.items() if entry["job_id"] == job_id]
        for dataset_id in [d for d in red if d in outputs] or outputs:
            gated[dataset_id] = since
    return gated


def status(dataset_id: str) -> dict[str, Any]:
    if mode() == "offline":
        return stub("status", dict(FRESH), dataset_id=dataset_id)
    registry = load_registry()
    if dataset_id not in registry:
        raise KeyError(dataset_id)
    graph = lineage_graph(str(contracts_dir()), str(jobs_dir()))
    try:
        gated = gated_datasets(registry)
    except Exception as e:
        log.warning("stale state unavailable for %s: %s", dataset_id, e)
        return dict(FRESH)
    hits = sorted(d for d in {dataset_id} | ancestors(graph, dataset_id) if d in gated)
    if not hits:
        return dict(FRESH)
    return {
        "stale": True,
        "since": min(gated[d] for d in hits),
        "cause": "quality check failed on " + ", ".join(f"`{d}`" for d in hits),
        "datasets": hits,
    }
