import os
import uuid

import psycopg
import pytest

import fabric_control as fc
from fabric_control.models import GateFailed
from pipelines import io
from pipelines.io.spark import get_spark
from pipelines.io.storage import ensure_bucket
from pipelines.jobs.ingest.load import ingest_load

DATASET = f"raw/_e2e/orders_{uuid.uuid4().hex[:8]}"
SCHEMA = "order_id INT, status STRING"


def query(sql: str, *params):
    with psycopg.connect(os.environ["SERVING_DB_DSN"]) as conn:
        return conn.execute(sql, params).fetchall()


@pytest.fixture(autouse=True)
def setup(registry):
    fc.run_migrations()
    ensure_bucket()
    registry(
        {DATASET: f"lake_raw.default.lake.{DATASET.rsplit('/', 1)[1]}"},
        {DATASET: [("order_id", "int"), ("status", "string")]},
    )


def load(rows, version, baseline, schema=SCHEMA):
    with fc.run("ingest/_e2e", {"mode": "full"}) as run:
        source = get_spark("e2e_raw").createDataFrame(rows, schema)
        check = ingest_load(run, DATASET, source, "e2e", version, {DATASET: baseline})
    return run, check


def latest():
    return {r.order_id: r.status for r in io.read_raw(DATASET).collect()}


def test_raw_ingest_flow():
    run, first = load([(1, "new"), (2, "new")], 1, 2)
    assert first.passed
    assert query("SELECT status, rows_in, rows_out FROM ops.runs WHERE run_id = %s", run.run_id) == [("success", 2, 2)]
    assert query("SELECT delta_version FROM ops.runs WHERE run_id = %s", run.run_id)[0][0] is not None

    _, second = load([(1, "shipped"), (2, "new")], 2, 2)
    assert second.passed
    assert io.read_delta(DATASET).count() == 4
    assert latest() == {1: "shipped", 2: "new"}
    assert {r._schema_version for r in io.read_delta(DATASET).collect()} == {"1.0.0"}

    _, bad = load([(1, "lost")], 3, 2)
    assert not bad.passed and "baseline 2" in bad.reason
    passed = query("SELECT passed FROM ops.load_reconciliation WHERE load_id = %s", bad.load_id)
    assert passed == [(False,)]
    assert latest() == {1: "shipped", 2: "new"}


def test_schema_drift_gates_the_load():
    load([(1, "new")], 1, None)
    before = io.read_delta(DATASET).count()
    with pytest.raises(GateFailed), fc.run("ingest/_e2e_drift", {"mode": "full"}) as run:
        source = get_spark("e2e_raw").createDataFrame([(1, "renamed")], "order_id INT, state STRING")
        ingest_load(run, DATASET, source, "e2e", 9, {})
    assert query("SELECT status FROM ops.runs WHERE run_id = %s", run.run_id) == [("gated",)]
    reason = query("SELECT reason FROM ops.load_reconciliation WHERE run_id = %s", run.run_id)[0][0]
    assert reason.startswith("schema_drift") and "status" in reason
    assert io.read_delta(DATASET).count() == before


def test_failed_run_writes_alert():
    with pytest.raises(RuntimeError), fc.run("ingest/_e2e_fail", {"mode": "full"}) as run:
        run.step = "read_source"
        raise RuntimeError("source unreachable")
    status = query("SELECT status, failing_step FROM ops.runs WHERE run_id = %s", run.run_id)
    assert status == [("failed", "read_source")]
    alerts = query("SELECT severity, message FROM ops.alerts WHERE run_id = %s", run.run_id)
    assert alerts == [("critical", "RuntimeError: source unreachable")]
