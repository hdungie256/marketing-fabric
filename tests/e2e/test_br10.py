from decimal import Decimal

import psycopg
import pytest
import yaml

from fabric_control.clients import postgres
from fabric_control.config import ROOT
from fabric_control.policy import load_policy

MARKS = yaml.safe_load((ROOT / "governance" / "baselines.yml").read_text())["spend"]


def as_role(conn, role, query):
    with conn.transaction(force_rollback=True):
        conn.execute(f"SET LOCAL ROLE {load_policy().roles[role]}")
        return conn.execute(query).fetchall()


@pytest.fixture(scope="module")
def conn():
    with postgres.connect() as connection:
        yield connection


def test_allocated_plus_unallocated_is_online_spend_every_day(conn):
    rows = as_role(conn, "UG04", "SELECT allocated, unallocated, online_spend FROM mart_shared_v.spend_reconciliation")
    assert len(rows) == 365
    assert all(a + u == o for a, u, o in rows)
    totals = [sum(r[i] for r in rows) for i in range(3)]
    assert totals == [Decimal(str(MARKS[k])) for k in ("allocated_total", "unallocated_total", "online_total")]


def test_budget_daily_spend_matches_shared_mart_and_budget_stays_apart(conn):
    allocated = as_role(conn, "UG04", "SELECT sum(allocated) FROM mart_finance_v.budget_daily")[0][0]
    assert allocated == Decimal(str(MARKS["allocated_total"]))
    budgets = as_role(conn, "UG04", "SELECT DISTINCT campaign_id, campaign_budget FROM mart_finance_v.budget_daily")
    assert len(budgets) == len({c for c, _ in budgets}) == 5


def test_marketing_analyst_cannot_read_finance_marts(conn):
    with pytest.raises(psycopg.errors.InsufficientPrivilege):
        as_role(conn, "UG01", "SELECT count(*) FROM mart_finance_v.budget_daily")
