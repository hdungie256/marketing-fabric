import os

import psycopg
import pytest

import fabric_control as fc
from app.services.comparison import METRICS

VIEW = "mart_campaign_v.comparison"
DSN = os.environ.get("SERVING_DB_DSN", "")


def as_role(login, query, *params):
    with psycopg.connect(DSN) as conn, conn.transaction(force_rollback=True):
        conn.execute(f"SET LOCAL ROLE {login}")
        return conn.execute(query, params).fetchall()


@pytest.mark.parametrize("login", ["marketing_manager", "marketing_analyst"])
def test_manager_and_analyst_read_grid(login):
    assert as_role(login, f"SELECT count(*) FROM {VIEW}") == [(5 * 8,)]


@pytest.mark.parametrize("column", METRICS)
def test_every_metric_column_maps_to_a_term(column):
    term = fc.term(column)
    assert term is not None and term["column"] == column
