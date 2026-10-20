from airflow.sdk import dag
from fabric.job_task import job_task, step_tasks


@dag(schedule=None, catchup=False, max_active_runs=1, is_paused_upon_creation=False, tags=["platform"])
def partial_refresh():
    plan = job_task("platform/affected", args=["--event", "{{ dag_run.conf | tojson }}"])
    step_tasks(plan.output)


partial_refresh()
