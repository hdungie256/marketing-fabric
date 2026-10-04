import json
import os
from typing import Any

from airflow.providers.docker.operators.docker import DockerOperator
from docker.types import Mount

FORWARDED_ENV = (
    "FABRIC_CONTROL_MODE",
    "SERVING_DB_DSN",
    "SOURCES_DB_DSN",
    "S3_ENDPOINT",
    "S3_BUCKET",
    "SOURCES_BUCKET",
    "AWS_ACCESS_KEY_ID",
    "AWS_SECRET_ACCESS_KEY",
    "OM_URL",
    "AIRFLOW_URL",
    "API_URL",
)
RESULT_PATH = "/tmp/fabric_result.pkl"


def job_task(job_id: str, scope: dict[str, Any] | None = None, **kwargs: Any) -> DockerOperator:
    command = ["python", "-m", f"pipelines.jobs.{job_id.replace('/', '.')}.job"]
    if scope is not None:
        command += ["--scope", json.dumps(scope)]
    return DockerOperator(
        task_id=job_id.replace("/", "."),
        image=os.environ["FABRIC_JOBS_IMAGE"],
        command=command,
        network_mode=os.environ["FABRIC_NETWORK"],
        environment={"FABRIC_DAG_RUN_ID": "{{ run_id }}", "FABRIC_RESULT_PATH": RESULT_PATH},
        private_environment={key: os.environ[key] for key in FORWARDED_ENV if key in os.environ},
        mounts=[Mount(target="/run/om", source=os.environ["FABRIC_SECRETS_VOLUME"], type="volume", read_only=True)],
        auto_remove="success",
        mount_tmp_dir=False,
        retrieve_output=True,
        retrieve_output_path=RESULT_PATH,
        mem_limit="3g",
        pool="fabric_writes",
        **kwargs,
    )
