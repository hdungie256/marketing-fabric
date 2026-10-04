import os
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from typing import Any

from fabric_control.clients import postgres
from fabric_control.config import log, mode, stub
from fabric_control.models import GateFailed, Scope


class Run:
    def __init__(self, job_id: str, scope: Scope):
        dag_run_id = os.environ.get("FABRIC_DAG_RUN_ID") or f"manual__{datetime.now(UTC):%Y%m%dT%H%M%S%f}"
        self.job_id = job_id
        self.scope = scope
        self.run_id = f"{dag_run_id}:{job_id}"
        self.event_id = os.environ.get("FABRIC_EVENT_ID")
        self.step: str | None = None
        self.rows_in: int | None = None
        self.rows_out: int | None = None
        self.delta_version: int | None = None

    def record_change(self, dataset_id: str, before: Any, after: Any) -> None:
        stub("record_change", run_id=self.run_id, dataset_id=dataset_id)

    def finish(self, status: str, failing_step: str | None = None) -> None:
        postgres.end_run(self.run_id, status, self.rows_in, self.rows_out, failing_step, self.delta_version)


@contextmanager
def run(job_id: str, scope: Scope) -> Iterator[Run]:
    current = Run(job_id, scope)
    if mode() == "offline":
        stub("run.start", run_id=current.run_id, scope=scope)
        yield current
        stub("run.end", run_id=current.run_id)
        return
    postgres.start_run(current.run_id, job_id, current.event_id, scope)
    try:
        yield current
    except GateFailed as exc:
        current.finish("gated", current.step)
        postgres.add_alert(current.run_id, job_id, "warning", str(exc))
        raise
    except Exception as exc:
        log.error("run %s failed: %s", current.run_id, exc)
        current.finish("failed", current.step)
        postgres.add_alert(current.run_id, job_id, "critical", f"{type(exc).__name__}: {exc}")
        raise
    current.finish("success")
