import functools
from typing import Any

from fabric_control.catalog import ancestors, layer, upstream_graph
from fabric_control.clients import postgres
from fabric_control.config import contracts_dir, jobs_dir, log, mode, stub
from fabric_control.manifests import load_manifests
from fabric_control.models import Event, Scope
from fabric_control.registry import load_registry

FRESH = {"stale": False, "since": None, "cause": None, "datasets": []}
FULL = {"mode": "full"}
LAYERS = ("raw", "unified", "mart")


def descendants(graph: dict[str, set[str]], dataset_id: str) -> set[str]:
    return {d for d in graph if dataset_id in ancestors(graph, d)}


def topological(graph: dict[str, set[str]], datasets: set[str]) -> list[str]:
    def rank(dataset_id: str) -> tuple[int, int, str]:
        shared = 0 if dataset_id.startswith("mart_shared.") else 1
        return LAYERS.index(layer(dataset_id)), shared, dataset_id

    pending = {d: graph.get(d, set()) & datasets for d in datasets}
    ordered: list[str] = []
    while pending:
        ready = sorted((d for d, upstream in pending.items() if not upstream - set(ordered)), key=rank)
        if not ready:
            raise ValueError(f"lineage cycle between {sorted(pending)}")
        ordered.append(ready[0])
        del pending[ready[0]]
    return ordered


def project(keys: dict[str, list[Any]], manifest: dict[str, Any] | None) -> Scope:
    if not manifest or "scope" not in manifest.get("modes", []):
        return dict(FULL)
    scope_map = manifest.get("scope_map") or {}
    projected = {scope_map[k]: values for k, values in keys.items() if k in scope_map}
    return {"mode": "scope", "keys": projected} if projected else dict(FULL)


def affected_by(event: Event) -> list[dict[str, Any]]:
    registry = load_registry()
    source = event["source"]
    if source not in registry:
        raise KeyError(source)
    keys = {k: v if isinstance(v, list) else [v] for k, v in event["keys"].items()}
    graph = upstream_graph(registry)
    manifests = load_manifests()
    affected = [{"dataset_id": source, "job_id": registry[source]["job_id"], "scope": dict(FULL)}]
    for dataset_id in topological(graph, descendants(graph, source)):
        scope = project(keys, manifests.get(dataset_id))
        affected.append({"dataset_id": dataset_id, "job_id": registry[dataset_id]["job_id"], "scope": scope})
    return affected


def merge(scopes: list[Scope]) -> Scope:
    if any(s.get("mode") != "scope" for s in scopes):
        return dict(FULL)
    keys: dict[str, list[Any]] = {}
    for scope in scopes:
        for column, values in scope["keys"].items():
            current = keys.setdefault(column, [])
            current += [v for v in values if v not in current]
    return {"mode": "scope", "keys": keys}


def refresh_plan(affected: list[dict[str, Any]]) -> list[dict[str, Any]]:
    jobs: dict[str, list[Scope]] = {}
    for item in affected:
        jobs.setdefault(item["job_id"], []).append(item["scope"])
    return [{"job_id": job_id, "scope": merge(scopes)} for job_id, scopes in jobs.items()]


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
