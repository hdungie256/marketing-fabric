import pytest

from fabric_control.clients import postgres
from fabric_control.policy import load_policy

SKU_COST = "SELECT reference_cogs, reference_cogs__denied FROM mart_finance_v.contribution_sku WHERE cost_available"


def as_role(conn, role, query):
    with conn.transaction(force_rollback=True):
        conn.execute(f"SET LOCAL ROLE {load_policy().roles[role]}")
        return conn.execute(query).fetchall()


@pytest.fixture(scope="module")
def conn():
    with postgres.connect() as connection:
        yield connection


def test_finance_sees_sku_cost_manager_sees_only_aggregate(conn):
    finance = as_role(conn, "UG04", SKU_COST)
    assert finance and all(cogs is not None and not denied for cogs, denied in finance)
    manager = as_role(conn, "UG03", SKU_COST)
    assert manager and all(cogs is None and denied for cogs, denied in manager)
    totals = as_role(conn, "UG03", "SELECT estimated_contribution, reference_cogs FROM mart_finance_v.contribution")
    assert len(totals) == 5 and all(c is not None and r is not None for c, r in totals)


def test_contribution_reconciles_to_its_parts(conn):
    rows = as_role(
        conn,
        "UG04",
        "SELECT attributed_gross_value - reference_cogs - campaign_cost = estimated_contribution "
        "FROM mart_finance_v.contribution",
    )
    assert rows and all(ok for (ok,) in rows)
