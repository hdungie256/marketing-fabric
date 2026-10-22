from airflow.sdk import dag
from fabric.job_task import job_task


@dag(schedule=None, catchup=False, max_active_runs=1, is_paused_upon_creation=False, tags=["platform"])
def partial_refresh():
    job_task("platform/partial_refresh", args=["--event", "{{ dag_run.conf | tojson }}"])


partial_refresh()
