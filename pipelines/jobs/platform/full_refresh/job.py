"""DAG full_refresh (NFR-4): every registry job as a full refresh, in dependency order, in this one process.
A step needs its direct upstream jobs; a skipped step writes no ops.runs row, so its descendants skip as well."""

from pipelines.dags.job_graph import job_graph, order
from pipelines.io.lineage import ROOT
from pipelines.jobs.platform.partial_refresh.job import run_plan

OUTPUTS = []


def plan(graph: dict[str, set[str]]) -> list[dict]:
    return [{"job_id": job_id, "scope": {"mode": "full"}, "needs": sorted(graph[job_id])} for job_id in order(graph)]


def main() -> None:
    run_plan(plan(job_graph(ROOT)))


if __name__ == "__main__":
    main()
