import os
from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from datetime import UTC, datetime
from typing import Any

from fabric_control.clients import postgres
from fabric_control.config import log, mode, stub
from fabric_control.models import GateFailed, Scope

_run_id: ContextVar[str | None] = ContextVar("run_id", default=None)


def current_run_id() -> str:
    run_id = _run_id.get()
    if run_id is None:
        raise RuntimeError("no active fabric_control.run()")
    return run_id


class Run:
    def __init__(self, job_id: str, scope: Scope):
        dag_run_id = os.environ.get("FABRIC_DAG_RUN_ID") or f"manual__{datetime.now(UTC):%Y%m%dT%H%M%S%f}"
        self.job_id = job_id
        self.scope = scope
        self.run_id = f"{dag_run_id}:{job_id}"
        self.event_id = os.environ.get("FABRIC_EVENT_ID") or None
        self.step: str | None = None
        self.rows_in: int | None = None
        self.rows_out: int | None = None
        self.delta_version: int | None = None
        self.delta_version_before: int | None = None

    def record_change(self, dataset_id: str, before: list[dict[str, Any]], after: list[dict[str, Any]]) -> int:
        if mode() == "offline":
            return stub("record_change", 0, run_id=self.run_id, dataset_id=dataset_id)
        from fabric_control.changes import metric_changes

        changes = metric_changes(dataset_id, before, after)
        postgres.insert_metric_changes(self.run_id, self.event_id, dataset_id, changes)
        log.info("run %s: %s metric values changed in %s", self.run_id, len(changes), dataset_id)
        return len(changes)

    def warn(self, message: str) -> None:
        if mode() == "offline":
            log.warning("run %s: %s", self.run_id, message)
            return
        postgres.add_alert(self.run_id, self.job_id, "warning", message)

    def finish(self, status: str, failing_step: str | None = None) -> None:
        postgres.end_run(
            self.run_id,
            status,
            self.rows_in,
            self.rows_out,
            failing_step,
            self.delta_version,
            self.delta_version_before,
        )


@contextmanager
def run(job_id: str, scope: Scope) -> Iterator[Run]:
    current = Run(job_id, scope)
    token = _run_id.set(current.run_id)
    try:
        yield from _run(current)
    finally:
        _run_id.reset(token)


def _run(current: Run) -> Iterator[Run]:
    job_id, scope = current.job_id, current.scope
    if mode() == "offline":
        stub("run.start", run_id=current.run_id, scope=scope)
        yield current
        stub("run.end", run_id=current.run_id)
        return
    postgres.start_run(current.run_id, job_id, current.event_id, scope)
    try:
        yield current
    except GateFailed as exc:
        current.finish("gated", ", ".join(exc.rules) or current.step)
        postgres.add_alert(current.run_id, job_id, "warning", str(exc))
        raise
    except Exception as exc:
        log.error("run %s failed: %s", current.run_id, exc)
        current.finish("failed", current.step)
        postgres.add_alert(current.run_id, job_id, "critical", f"{type(exc).__name__}: {exc}")
        raise
    current.finish("success")
