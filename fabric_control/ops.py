import os
from typing import Any

from fabric_control.clients import airflow, postgres
from fabric_control.config import mode, stub


def trigger(dag_id: str, conf: dict[str, Any]) -> str:
    if mode() == "offline":
        return stub("trigger", "offline", dag_id=dag_id, conf=conf)
    return airflow.trigger_dag(dag_id, conf)


def record_event(event: dict[str, Any], dag_run_id: str | None) -> None:
    if mode() == "offline":
        stub("record_event", event=event, dag_run_id=dag_run_id)
        return
    postgres.insert_event(event, dag_run_id)


def record_timing(page: str, ms: float) -> None:
    if mode() == "offline":
        stub("record_timing", page=page, ms=ms)
        return
    import psycopg

    with psycopg.connect(
        host=os.environ.get("DB_HOST", "postgresql"),
        port=int(os.environ.get("DB_PORT", "5432")),
        dbname="serving",
        user="ops_writer",
        password=os.environ["OPS_WRITER_DB_PASSWORD"],
        autocommit=True,
    ) as conn:
        conn.execute("INSERT INTO ops.page_timings (page, ms) VALUES (%s, %s)", (page, round(ms, 1)))
