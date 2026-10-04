from airflow.sdk import dag, task
from fabric.job_task import job_task


@dag(schedule=None, catchup=False, is_paused_upon_creation=False, tags=["platform"])
def platform_smoke():
    smoke = job_task("smoke")

    @task
    def check(result: dict) -> int:
        if not result or result["rows"] < 1:
            raise ValueError(f"smoke job returned {result}")
        return result["rows"]

    check(smoke.output)


platform_smoke()
