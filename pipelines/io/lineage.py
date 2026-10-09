from collections.abc import Callable

from fabric_control.config import ROOT
from pipelines.dags.job_graph import declared


def job_inputs(job_id: str) -> list[str]:
    return declared(ROOT / "pipelines" / "jobs" / job_id / "job.py", "INPUTS")


def raw_ancestors(dataset_ids: list[str], writers: dict[str, str], inputs_of: Callable[[str], list[str]]) -> list[str]:
    found, seen, pending = set(), set(), list(dataset_ids)
    while pending:
        dataset_id = pending.pop()
        if dataset_id in seen:
            continue
        seen.add(dataset_id)
        if dataset_id not in writers:
            raise ValueError(f"{dataset_id} is not in the registry")
        if dataset_id.startswith("raw/"):
            found.add(dataset_id)
        else:
            pending += inputs_of(writers[dataset_id])
    return sorted(found)
