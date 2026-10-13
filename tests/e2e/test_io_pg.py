import os

import psycopg
import pytest

from pipelines import io
from pipelines.jobs.marts.campaign.campaign_overview import job

TABLE = "mart_campaign.campaign_overview"
COLS = (
    "period_id, period_label, period_start, period_end, campaign_id, campaign_name, attributed_orders, "
    "attributed_buyers, attributed_gross_value, average_order_value, provenance"
)


def query(sql):
    with psycopg.connect(os.environ["SERVING_DB_DSN"]) as conn:
        return conn.execute(sql).fetchall()


def snapshot():
    return query(f"SELECT {COLS} FROM {TABLE} ORDER BY period_id, campaign_id")


def test_rerun_is_deterministic():
    job.main({"mode": "full"})
    first = snapshot()
    job.main({"mode": "full"})
    assert snapshot() == first and len(first) == 30


def test_failed_write_keeps_previous_rows():
    before = snapshot()
    duplicate = io.get_spark().createDataFrame([before[0], before[0]], COLS.replace(" ", "").split(","))
    with pytest.raises(psycopg.Error):
        io.write_pg_full(TABLE, duplicate, "e2e-dup", {})
    assert snapshot() == before
