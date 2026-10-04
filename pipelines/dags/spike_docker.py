import os

from airflow.providers.docker.operators.docker import DockerOperator
from airflow.sdk import dag, task

ENV_KEYS = (
    "FABRIC_CONTROL_MODE",
    "SERVING_DB_DSN",
    "SOURCES_DB_DSN",
    "S3_ENDPOINT",
    "S3_BUCKET",
    "AWS_ACCESS_KEY_ID",
    "AWS_SECRET_ACCESS_KEY",
    "OM_URL",
    "AIRFLOW_URL",
    "API_URL",
)
RESULT = "/tmp/result.pkl"


@dag(schedule=None, catchup=False, is_paused_upon_creation=False, tags=["spike"])
def spike_docker():
    job = DockerOperator(
        task_id="spike",
        image=os.environ["FABRIC_JOBS_IMAGE"],
        command=f'spark-submit --master "local[*]" pipelines/jobs/spike/job.py {RESULT}',
        network_mode=os.environ["FABRIC_NETWORK"],
        private_environment={k: os.environ[k] for k in ENV_KEYS if k in os.environ},
        auto_remove="success",
        mount_tmp_dir=False,
        retrieve_output=True,
        retrieve_output_path=RESULT,
        mem_limit="3g",
    )

    @task
    def check(result: dict) -> int:
        assert result["rows"] > 0, result
        return result["rows"]

    check(job.output)


spike_docker()
