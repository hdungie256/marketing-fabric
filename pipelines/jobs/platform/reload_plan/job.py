"""Plan for the reload_source DAG (Story 7.3, FR-24): the source's ingest job, then every job downstream of it,
in dependency order and as full refreshes. Steps use the same shape as partial_refresh, so a failed step skips the
steps that need it."""

import argparse

from pipelines.dags.job_graph import job_graph, order
from pipelines.io.lineage import ROOT
from pipelines.io.result import write_result

OUTPUTS = []


def plan(source: str, graph: dict[str, set[str]]) -> list[dict]:
    root = f"ingest/{source}"
    if root not in graph:
        raise KeyError(f"no ingest job for source {source!r}")
    chosen = {root}
    for job_id in order(graph):
        if graph[job_id] & chosen:
            chosen.add(job_id)
    return [
        {"job_id": job_id, "scope": {"mode": "full"}, "needs": sorted(graph[job_id] & chosen)}
        for job_id in order(graph)
        if job_id in chosen
    ]


def main(source: str) -> list[dict]:
    steps = plan(source, job_graph(ROOT))
    for step in steps:
        print(f"{step['job_id']} after {step['needs']}", flush=True)
    write_result(steps)
    return steps


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", required=True)
    main(parser.parse_args().source)
