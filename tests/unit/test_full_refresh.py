import runpy
import sys
import types

import pytest

from fabric_control.models import GateFailed
from pipelines.dags import job_graph as job_graph_module
from pipelines.dags.job_graph import job_graph, order
from pipelines.io.lineage import ROOT
from pipelines.jobs.platform.full_refresh import job
from pipelines.jobs.platform.partial_refresh import job as runner
from pipelines.jobs.platform.refresh_step import job as refresh_step


def test_plan_runs_every_registry_job_once_after_its_direct_upstreams():
    graph = job_graph(ROOT)
    steps = job.plan(graph)
    jobs = [s["job_id"] for s in steps]
    assert sorted(jobs) == sorted(graph)
    for i, step in enumerate(steps):
        assert step["needs"] == sorted(graph[step["job_id"]])
        assert set(step["needs"]) <= set(jobs[:i]), step
    assert all(s["scope"] == {"mode": "full"} for s in steps)


def test_failed_job_skips_exactly_its_descendants_and_fails_the_task(monkeypatch):
    graph = job_graph(ROOT)
    statuses, ran = {}, []

    def run_module(name, run_name, alter_sys):  # stands in for the job: writes its ops.runs status
        job_id = sys.argv[0]
        ran.append(job_id)
        statuses[job_id] = "gated" if job_id == "unified/campaign_spend" else "success"
        if statuses[job_id] == "gated":
            raise GateFailed("unified/campaign_spend: critical rules failed")

    monkeypatch.setattr(sys, "argv", list(sys.argv))
    monkeypatch.setattr(refresh_step.runpy, "run_module", run_module)
    monkeypatch.setattr(refresh_step.fc, "blocked", lambda needs: [n for n in needs if statuses.get(n) != "success"])
    monkeypatch.setattr(runner, "clear_cache", lambda: None)
    with pytest.raises(SystemExit) as exit_:
        job.main()

    stopped = {"unified/campaign_spend"}
    for job_id in order(graph):
        if graph[job_id] & stopped:
            stopped.add(job_id)
    assert len(stopped) > 2 and set(ran) == (set(graph) - stopped) | {"unified/campaign_spend"}
    failed = str(exit_.value.code).removeprefix("did not succeed: ").split(", ")
    assert set(failed) == stopped


class Task:
    def __init__(self, task_id, **kwargs):
        self.task_id, self.kwargs, self.downstream = task_id, kwargs, set()

    def __rshift__(self, other):
        self.downstream |= {t.task_id for t in (other if isinstance(other, list) else [other])}
        return other


def build_dag(monkeypatch, per_job: str | None) -> dict[str, Task]:
    """Parse pipelines/dags/full_refresh.py with stand-ins for airflow.sdk and job_task; Airflow is not installed."""
    tasks = {}

    def job_task(job_id, **kwargs):
        tasks[job_id] = Task(job_id, **kwargs)
        return tasks[job_id]

    sdk = types.SimpleNamespace(dag=lambda **_: lambda fn: fn, task=lambda fn: lambda: job_task(fn.__name__))
    for name, module in {
        "airflow": types.SimpleNamespace(),
        "airflow.sdk": sdk,
        "fabric": types.SimpleNamespace(),
        "fabric.job_graph": job_graph_module,
        "fabric.job_task": types.SimpleNamespace(job_task=job_task),
    }.items():
        monkeypatch.setitem(sys.modules, name, module)
    monkeypatch.setenv("FABRIC_ROOT", str(ROOT))
    if per_job is None:
        monkeypatch.delenv("FABRIC_FULL_REFRESH_PER_JOB", raising=False)
    else:
        monkeypatch.setenv("FABRIC_FULL_REFRESH_PER_JOB", per_job)
    runpy.run_path(str(ROOT / "pipelines" / "dags" / "full_refresh.py"))
    return tasks


@pytest.mark.parametrize("per_job", [None, "0"])
def test_dag_runs_all_jobs_in_one_task_by_default(monkeypatch, per_job):
    tasks = build_dag(monkeypatch, per_job)
    assert set(tasks) == {"platform/full_refresh", "platform/catalog", "platform/policies", "jobs_passed"}
    assert tasks["platform/full_refresh"].downstream == {"platform/catalog", "platform/policies", "jobs_passed"}
    assert tasks["platform/catalog"].kwargs == tasks["platform/policies"].kwargs == {"trigger_rule": "all_done"}
    assert tasks["jobs_passed"].kwargs == {}  # all_success: the DAG run fails when the runner task fails


def test_escape_hatch_restores_one_task_per_job(monkeypatch):
    tasks = build_dag(monkeypatch, "1")
    graph = job_graph(ROOT)
    assert set(tasks) == set(graph) | {"platform/catalog", "platform/policies", "jobs_passed"}
    trailing = {"platform/catalog", "platform/policies", "jobs_passed"}
    for job_id in graph:
        assert tasks[job_id].downstream == trailing | {j for j in graph if job_id in graph[j]}
