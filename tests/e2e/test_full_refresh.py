import json
import os
import urllib.request

import psycopg
import pytest

import fabric_control as fc
from fabric_control import load_registry
from fabric_control.clients import airflow
from pipelines import io
from pipelines.jobs.ingest.reconciliation import load_baselines
from sources.seed import seed

DAG_ID = "full_refresh"


def query(sql: str, *params):
    with psycopg.connect(os.environ["SERVING_DB_DSN"]) as conn:
        return conn.execute(sql, params).fetchall()


def source_versions() -> dict[str, int]:
    with psycopg.connect(os.environ["SOURCES_DB_DSN"]) as conn:
        return dict(conn.execute("SELECT source, version FROM meta.source_versions").fetchall())


def latest_success() -> str | None:
    runs = airflow.call("GET", f"/api/v2/dags/{DAG_ID}/dagRuns?state=success&order_by=-start_date&limit=1")
    return runs["dag_runs"][0]["dag_run_id"] if runs["dag_runs"] else None


@pytest.fixture(scope="module")
def refresh():
    run_id = None if os.environ.get("FABRIC_E2E_FULL") == "1" else latest_success()
    if run_id:
        return run_id, source_versions()
    versions = seed()
    run_id = fc.trigger(DAG_ID, {})
    assert airflow.wait(DAG_ID, run_id, timeout=1800, poll=10) == "success"
    return run_id, versions


def test_every_ingest_job_succeeded(refresh):
    run_id, _ = refresh
    rows = query("SELECT job_id, status FROM ops.runs WHERE run_id LIKE %s", f"{run_id}:ingest/%")
    assert len(rows) == 7 and {status for _, status in rows} == {"success"}


def test_every_raw_load_reconciled_against_baseline(refresh):
    run_id, _ = refresh
    baselines = load_baselines()
    raw = {d for d in load_registry() if d.startswith("raw/")}
    checks = query(
        "SELECT dataset_id, passed, raw_rows FROM ops.load_reconciliation WHERE run_id LIKE %s", f"{run_id}:%"
    )
    assert {d for d, _, _ in checks} == raw
    assert all(passed for _, passed, _ in checks)
    assert {d: rows for d, _, rows in checks} == {d: baselines[d] for d in raw}


def test_raw_carries_seeded_source_version(refresh):
    _, versions = refresh
    latest = io.read_raw("raw/sales/sales_lines")
    assert latest.count() == 52924
    assert {r._source_version for r in latest.select("_source_version").distinct().collect()} == {versions["sales"]}


def test_derived_source_table_is_not_readable_as_fact(refresh):
    with pytest.raises(ValueError, match="derived"):
        io.read_raw("raw/spend/spend_recon")


def test_mock_api_serves_campaign_sources(refresh):
    _, versions = refresh
    with urllib.request.urlopen(f"{os.environ['API_URL']}/campaign/attribution") as response:
        body = json.loads(response.read())
    assert len(body["items"]) == 1290 and body["source_version"] == versions["campaign"]
