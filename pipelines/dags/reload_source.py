from airflow.sdk import dag
from fabric.job_task import job_task, step_tasks


@dag(schedule=None, catchup=False, max_active_runs=1, is_paused_upon_creation=False, tags=["platform"])
def reload_source():
    plan = job_task("platform/reload_plan", args=["--source", "{{ dag_run.conf['source'] }}"])
    step_tasks(plan.output)


reload_source()
