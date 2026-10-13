import os

import psycopg
import pytest

import fabric_control as fc

VIEW = "mart_campaign_v.campaign_overview"
DSN = os.environ.get("SERVING_DB_DSN", "")


def as_role(login, query, *params):
    with psycopg.connect(DSN) as conn, conn.transaction(force_rollback=True):
        conn.execute(f"SET LOCAL ROLE {login}")
        return conn.execute(query, params).fetchall()


def test_whole_period_totals_for_analyst():
    rows = as_role(
        "marketing_analyst",
        f"SELECT attributed_orders, attributed_buyers FROM {VIEW} WHERE period_id = 'FY2019' AND campaign_id = 'ALL'",
    )
    assert rows == [(1290, 456)]


def test_manager_reads_full_grid():
    assert as_role("marketing_manager", f"SELECT count(*) FROM {VIEW}") == [(30,)]


def test_finance_controller_is_denied():
    with pytest.raises(psycopg.errors.InsufficientPrivilege):
        as_role("finance_controller", f"SELECT count(*) FROM {VIEW}")


def test_record_timing_writes_page_timing():
    fc.record_timing("e2e_br01", 12.3)
    with psycopg.connect(DSN) as conn:
        assert conn.execute("SELECT count(*) FROM ops.page_timings WHERE page = 'e2e_br01'").fetchone()[0] >= 1
