import os

import psycopg
import pytest

import fabric_control as fc
from fabric_control.data_quality import break_dq
from fabric_control.models import GateFailed
from pipelines import io
from pipelines.jobs.unified.ref_category_map import job

DATASET = "unified/ref_category_map"
DESCENDANT = "unified/campaigns"


def latest_run():
    with psycopg.connect(os.environ["SERVING_DB_DSN"]) as conn:
        return conn.execute(
            "SELECT status, failing_step FROM ops.runs WHERE job_id = %s ORDER BY started_at DESC LIMIT 1",
            (job.JOB_ID,),
        ).fetchone()


def run_ids():
    return {row._run_id for row in io.read_delta(DATASET).select("_run_id").distinct().collect()}


def test_break_dq_gates_write_and_marks_descendants_stale():
    fc.run_migrations()
    job.main({"mode": "full"})
    written = run_ids()
    break_dq(DATASET)
    try:
        with pytest.raises(GateFailed):
            job.main({"mode": "full"})
        assert latest_run() == ("gated", "break_dq")
        assert run_ids() == written
        for dataset_id in (DATASET, DESCENDANT):
            state = fc.status(dataset_id)
            assert state["stale"] and state["datasets"] == [DATASET], dataset_id
            assert state["cause"] == f"quality check failed on `{DATASET}`"
        assert fc.status("raw/sales/sales_lines")["stale"] is False
    finally:
        break_dq(DATASET, on=False)
    job.main({"mode": "full"})
    assert latest_run() == ("success", None)
    assert fc.status(DESCENDANT)["stale"] is False
