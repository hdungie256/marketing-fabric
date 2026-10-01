from typing import Any

from fabric_control.config import stub
from fabric_control.models import Event


def affected_by(event: Event) -> list[dict[str, Any]]:
    return stub("affected_by", [], event=event)


def status(dataset_id: str) -> dict[str, Any]:
    return stub("status", {"stale": False, "since": None, "cause": None}, dataset_id=dataset_id)
