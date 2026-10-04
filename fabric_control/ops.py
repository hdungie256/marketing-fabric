from typing import Any

from fabric_control.clients import airflow
from fabric_control.config import mode, stub


def trigger(dag_id: str, conf: dict[str, Any]) -> str:
    if mode() == "offline":
        return stub("trigger", "offline", dag_id=dag_id, conf=conf)
    return airflow.trigger_dag(dag_id, conf)


def record_timing(page: str, ms: float) -> None:
    stub("record_timing", page=page, ms=ms)
