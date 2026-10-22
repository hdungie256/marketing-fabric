"""BR15 e2e (T-BR15): break a source, see the failure and its cause, clear it, reload, counts match the baselines."""

import os

import psycopg
import pytest

from fabric_control.clients import airflow
from sources.faults import set_fault

SOURCE = "spend"
DAG = "reload_source"


def query(sql, params=()):
    with psycopg.connect(os.environ["SERVING_DB_DSN"]) as conn:
        return conn.execute(sql, params).fetchall()


def reload() -> tuple[str, str]:
    run_id = airflow.trigger_dag(DAG, {"source": SOURCE}, wait_for_dag=120)
    return run_id, airflow.wait(DAG, run_id, timeout=900, poll=5)


@pytest.fixture
def broken_source():
    set_fault(SOURCE)
    yield
    set_fault(SOURCE, on=False)


def test_break_alert_fix_reload_reconciles(broken_source):
    run_id, state = reload()
    assert state == "failed"
    [(status, step, message)] = query(
        "SELECT r.status, r.failing_step, a.message FROM ops.runs r JOIN ops.alerts a USING (run_id) "
        "WHERE r.run_id = %s",
        (f"{run_id}:ingest/{SOURCE}",),
    )
    assert (status, step) == ("failed", f"connect {SOURCE}")
    assert "fault injected with make break-source" in message
    downstream = query(
        "SELECT count(*) FROM ops.runs WHERE run_id LIKE %s AND job_id <> %s", (f"{run_id}:%", f"ingest/{SOURCE}")
    )
    assert downstream == [(0,)]  # dependents were skipped, not run on stale input

    set_fault(SOURCE, on=False)
    run_id, state = reload()
    assert state == "success"
    loads = query(
        "SELECT dataset_id, passed, raw_rows, baseline_rows FROM ops.load_reconciliation WHERE run_id = %s",
        (f"{run_id}:ingest/{SOURCE}",),
    )
    assert {d for d, *_ in loads} == {
        f"raw/{SOURCE}/campaign_spend",
        f"raw/{SOURCE}/daily_spend",
        f"raw/{SOURCE}/spend_recon",
    }
    assert all(passed and raw == baseline for _, passed, raw, baseline in loads), loads
    latest = query(
        "SELECT status FROM ops.runs WHERE job_id = %s ORDER BY started_at DESC LIMIT 1", (f"ingest/{SOURCE}",)
    )
    assert latest == [("success",)]  # the UG06 alert indicator counts latest failed runs, so it clears
