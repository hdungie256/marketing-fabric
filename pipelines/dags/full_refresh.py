import os
from pathlib import Path

from airflow.sdk import dag, task
from fabric.job_graph import job_graph
from fabric.job_task import job_task

ROOT = Path(os.environ.get("FABRIC_ROOT", "/opt/fabric"))


@dag(schedule=None, catchup=False, max_active_runs=1, is_paused_upon_creation=False, tags=["platform"])
def full_refresh():
    @task
    def jobs_passed() -> None:
        pass

    if os.environ.get("FABRIC_FULL_REFRESH_PER_JOB") == "1":
        # Escape hatch: one fabric-jobs container per job, as before platform/full_refresh.
        graph = job_graph(ROOT)
        jobs = {job_id: job_task(job_id) for job_id in graph}
        for job_id, upstream in graph.items():
            for dependency in upstream:
                jobs[dependency] >> jobs[job_id]
    else:
        jobs = {"platform/full_refresh": job_task("platform/full_refresh")}
    catalog = job_task("platform/catalog", trigger_rule="all_done")
    policies = job_task("platform/policies", trigger_rule="all_done")
    passed = jobs_passed()
    for job in jobs.values():
        job >> [catalog, policies, passed]


full_refresh()
