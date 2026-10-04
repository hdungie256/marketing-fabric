import ast
from pathlib import Path

import yaml


class JobGraphError(Exception):
    pass


def declared(path: Path, name: str) -> list[str]:
    for node in ast.parse(path.read_text()).body:
        if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == name for t in node.targets):
            return list(ast.literal_eval(node.value))
    return []


def writers(root: Path) -> dict[str, str]:
    result = {}
    for path in sorted((root / "contracts" / "datasets").glob("*.yml")):
        for entry in (yaml.safe_load(path.read_text()) or {}).get("datasets") or []:
            result[entry["dataset_id"]] = entry["job_id"]
    return result


def order(graph: dict[str, set[str]]) -> list[str]:
    pending = {job: set(upstream) for job, upstream in graph.items()}
    ordered = []
    while pending:
        ready = sorted(job for job, upstream in pending.items() if not upstream)
        if not ready:
            raise JobGraphError(f"dependency cycle between {sorted(pending)}")
        ordered += ready
        for job in ready:
            del pending[job]
        for upstream in pending.values():
            upstream.difference_update(ready)
    return ordered


def job_graph(root: Path) -> dict[str, set[str]]:
    dataset_writers = writers(root)
    graph = {}
    for job_id in sorted(set(dataset_writers.values())):
        path = root / "pipelines" / "jobs" / job_id / "job.py"
        if not path.exists():
            raise JobGraphError(f"registry job {job_id} has no {path.relative_to(root)}")
        inputs = declared(path, "INPUTS")
        unknown = [d for d in inputs if d not in dataset_writers]
        if unknown:
            raise JobGraphError(f"{job_id} reads unregistered datasets {unknown}")
        graph[job_id] = {dataset_writers[d] for d in inputs} - {job_id}
    order(graph)
    return graph
