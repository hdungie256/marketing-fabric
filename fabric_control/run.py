import os
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from typing import Any

from fabric_control.config import log, stub
from fabric_control.models import Scope


class Run:
    def __init__(self, job_id: str, scope: Scope):
        dag_run_id = os.environ.get("FABRIC_DAG_RUN_ID") or f"manual__{datetime.now(UTC):%Y%m%dT%H%M%S}"
        self.job_id = job_id
        self.scope = scope
        self.run_id = f"{dag_run_id}:{job_id}"

    def record_change(self, dataset_id: str, before: Any, after: Any) -> None:
        stub("record_change", run_id=self.run_id, dataset_id=dataset_id)


@contextmanager
def run(job_id: str, scope: Scope) -> Iterator[Run]:
    current = Run(job_id, scope)
    stub("run.start", run_id=current.run_id, scope=scope)
    try:
        yield current
    except Exception as exc:
        log.error("run %s failed: %s", current.run_id, exc)
        raise
    stub("run.end", run_id=current.run_id)
