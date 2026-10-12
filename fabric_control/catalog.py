from dataclasses import dataclass, field
from typing import Any

from fabric_control.clients import openmetadata, postgres
from fabric_control.clients.http import HttpError
from fabric_control.config import jobs_dir, log, mode
from fabric_control.decisions.scoring import score
from fabric_control.glossary import load_terms
from fabric_control.models import DataQualityResult, RuleResult, Status
from fabric_control.registry import load_registry
from pipelines.dags.job_graph import declared

NOT_MEASURED = "not yet measured"


def layer(dataset_id: str) -> str:
    return dataset_id.split("/")[0].split(".")[0].split("_")[0]


def upstream_graph(registry: dict[str, dict]) -> dict[str, set[str]]:
    graph = {}
    for dataset_id, entry in registry.items():
        path = jobs_dir() / entry["job_id"] / "job.py"
        inputs = declared(path, "INPUTS") if path.exists() else []
        graph[dataset_id] = {d for d in inputs if d in registry and d != dataset_id}
    return graph


def ancestors(graph: dict[str, set[str]], dataset_id: str) -> set[str]:
    seen: set[str] = set()
    pending = list(graph.get(dataset_id, ()))
    while pending:
        current = pending.pop()
        if current not in seen:
            seen.add(current)
            pending += graph.get(current, ())
    return seen


@dataclass
class Snapshot:
    registry: dict[str, dict] = field(default_factory=load_registry)
    refreshed: dict[str, tuple[Any, int | None]] = field(default_factory=dict)
    quality: dict[str, list[tuple[str, str, bool]]] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.graph = upstream_graph(self.registry)

    def sources(self, dataset_id: str) -> list[str]:
        lineage = {dataset_id} | ancestors(self.graph, dataset_id)
        return sorted({d.split("/")[1] for d in lineage if layer(d) == "raw"})

    def provenance(self, dataset_id: str) -> str:
        lineage = {dataset_id} | ancestors(self.graph, dataset_id)
        synthetic = any(layer(d) == "raw" and self.registry[d].get("synthetic_source") for d in lineage)
        return "synthetic" if synthetic else "original"

    def score(self, dataset_id: str) -> tuple[float, Status] | str:
        rules = self.quality.get(self.registry[dataset_id]["om_fqn"])
        if not rules:
            return NOT_MEASURED
        return score(DataQualityResult(dataset_id, {}, [RuleResult(*rule) for rule in rules]))

    def item(self, dataset_id: str) -> dict[str, Any]:
        entry = self.registry[dataset_id]
        refreshed_at, version = self.refreshed.get(entry["job_id"], (None, None))
        quality = self.score(dataset_id)
        measured = quality != NOT_MEASURED
        return {
            "dataset_id": dataset_id,
            "layer": layer(dataset_id),
            "description": entry.get("description", ""),
            "owner": entry.get("owner"),
            "sources": self.sources(dataset_id),
            "provenance": self.provenance(dataset_id),
            "refreshed_at": refreshed_at,
            "version": version,
            "score": quality[0] if measured else None,
            "status": quality[1] if measured else NOT_MEASURED,
        }


def snapshot() -> Snapshot:
    current = Snapshot()
    if mode() == "offline":
        return current
    try:
        current.refreshed = postgres.last_success()
    except Exception as e:
        log.warning("refresh times unavailable: %s", e)
    try:
        current.quality = openmetadata.test_results()
    except (HttpError, OSError) as e:
        log.warning("quality results unavailable: %s", e)
    return current


def catalog(filter: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    current = snapshot()
    items = [current.item(d) for d in sorted(current.registry)]
    return [i for i in items if all(i.get(k) == v for k, v in (filter or {}).items())]


def latest_score(dataset_id: str) -> tuple[float, Status] | str:
    current = snapshot()
    if dataset_id not in current.registry:
        raise KeyError(dataset_id)
    return current.score(dataset_id)


def term(term_id: str) -> dict[str, Any] | None:
    current = snapshot()
    entry = load_terms(registry=current.registry).get(term_id)
    if entry is None:
        return None
    dataset = current.item(entry["dataset_id"])
    result = {k: v for k, v in entry.items() if not k.startswith("_")}
    for key in ("provenance", "refreshed_at", "score", "status"):
        result[key] = dataset[key]
    result["synthetic"] = dataset["provenance"] == "synthetic"
    return result


def search(q: str) -> list[dict[str, Any]]:
    needle = q.strip().lower()
    if not needle:
        return []
    registry = load_registry()
    hits = [
        {"kind": "dataset", "id": d, "name": d, "description": e.get("description", "")}
        for d, e in sorted(registry.items())
        if needle in d.lower() or needle in e.get("description", "").lower()
    ]
    for key, entry in sorted(load_terms(registry=registry).items()):
        text = " ".join(str(entry.get(f, "")) for f in ("display_name", "definition", "formula")).lower()
        if needle in key or needle in text:
            hits.append(
                {"kind": "term", "id": key, "name": entry["display_name"], "description": entry.get("definition", "")}
            )
    return hits


def static_edges(current: Snapshot, dataset_id: str, depth: int) -> list[tuple[str, str, str | None]]:
    downstream: dict[str, set[str]] = {}
    for target, inputs in current.graph.items():
        for source in inputs:
            downstream.setdefault(source, set()).add(target)
    edges = set()
    for neighbours, upward in ((current.graph, True), (downstream, False)):
        frontier = {dataset_id}
        for _ in range(depth):
            reached = set()
            for node in frontier:
                for other in neighbours.get(node, ()):
                    source, target = (other, node) if upward else (node, other)
                    edges.add((source, target, current.registry[target]["job_id"]))
                    reached.add(other)
            frontier = reached
    return sorted(edges, key=lambda e: (e[0], e[1]))


def online_edges(current: Snapshot, dataset_id: str, depth: int) -> list[tuple[str, str, str | None]]:
    by_fqn = {e["om_fqn"]: d for d, e in current.registry.items()}
    edges = openmetadata.lineage_edges(current.registry[dataset_id]["om_fqn"], depth)
    known = {(by_fqn[s], by_fqn[t], job) for s, t, job in edges if s in by_fqn and t in by_fqn}
    return sorted(known, key=lambda e: (e[0], e[1]))


def lineage(dataset_id: str, depth: int = 1) -> dict[str, list]:
    current = snapshot()
    if dataset_id not in current.registry:
        raise KeyError(dataset_id)
    edges = static_edges(current, dataset_id, depth)
    if mode() != "offline":
        try:
            edges = online_edges(current, dataset_id, depth)
        except (HttpError, OSError) as e:
            log.warning("lineage for %s read from job declarations: %s", dataset_id, e)
    nodes = sorted({dataset_id} | {d for s, t, _ in edges for d in (s, t)})
    return {
        "nodes": [current.item(d) for d in nodes],
        "edges": [{"from": s, "to": t, "job_id": job} for s, t, job in edges],
    }
