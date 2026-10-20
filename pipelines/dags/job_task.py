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
STEP_MODULE = "pipelines.jobs.platform.refresh_step.job"
SKIPPED = 99


def module(job_id: str) -> str:
    return f"pipelines.jobs.{job_id.replace('/', '.')}.job"


def options() -> dict[str, Any]:
    return {
        "image": os.environ["FABRIC_JOBS_IMAGE"],
        "network_mode": os.environ["FABRIC_NETWORK"],
        "environment": {
            "FABRIC_DAG_RUN_ID": "{{ run_id }}",
            "FABRIC_EVENT_ID": "{{ (dag_run.conf or {}).get('event_id', '') }}",
            "FABRIC_RESULT_PATH": RESULT_PATH,
        },
        "private_environment": {key: os.environ[key] for key in FORWARDED_ENV if key in os.environ},
        "mounts": [Mount(target="/run/om", source=os.environ["FABRIC_SECRETS_VOLUME"], type="volume", read_only=True)],
        "auto_remove": "success",
        "mount_tmp_dir": False,
        "retrieve_output": True,
        "retrieve_output_path": RESULT_PATH,
        "mem_limit": "3g",
        "pool": "fabric_writes",
    }


def job_task(
    job_id: str, scope: dict[str, Any] | None = None, args: list[str] | None = None, **kwargs: Any
) -> DockerOperator:
    command = ["python", "-m", module(job_id), *(args or [])]
    if scope is not None:
        command += ["--scope", json.dumps(scope)]
    return DockerOperator(task_id=job_id.replace("/", "."), command=command, **options(), **kwargs)


def step_command(step: dict[str, Any]) -> list[str]:
    scope, needs = json.dumps(step["scope"]), json.dumps(step["needs"])
    return ["python", "-m", STEP_MODULE, step["job_id"], "--scope", scope, "--needs", needs]


def step_tasks(plan: Any) -> Any:
    return DockerOperator.partial(
        task_id="refresh",
        max_active_tis_per_dagrun=1,
        skip_on_exit_code=SKIPPED,
        map_index_template="{{ task.command[3] }}",
        **options(),
    ).expand(command=plan.map(step_command))
