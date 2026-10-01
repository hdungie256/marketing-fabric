from typing import Any

from fabric_control.config import stub


def trigger(dag_id: str, conf: dict[str, Any]) -> str:
    return stub("trigger", "offline", dag_id=dag_id, conf=conf)


def record_timing(page: str, ms: float) -> None:
    stub("record_timing", page=page, ms=ms)
