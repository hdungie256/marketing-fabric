from airflow.sdk import dag, task
from fabric.job_task import job_task

INGEST = ("sales", "crm", "erp", "campaign", "promotion", "spend", "tax")


@dag(schedule=None, catchup=False, max_active_runs=1, is_paused_upon_creation=False, tags=["platform"])
def full_refresh():
    @task
    def loads_passed() -> None:
        pass

    ingest = [job_task(f"ingest/{source}") for source in INGEST]
    ingest >> job_task("platform/catalog", trigger_rule="all_done")
    ingest >> loads_passed()


full_refresh()
