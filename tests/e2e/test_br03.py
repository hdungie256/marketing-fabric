import os

import psycopg
import pytest

VIEW = "mart_campaign_v.product_sales"
DSN = os.environ.get("SERVING_DB_DSN", "")


def as_role(login, query, *params):
    with psycopg.connect(DSN) as conn, conn.transaction(force_rollback=True):
        conn.execute(f"SET LOCAL ROLE {login}")
        return conn.execute(query, params).fetchall()


def test_nest_categories_separate_in_view():
    rows = as_role(
        "marketing_analyst",
        f"SELECT DISTINCT canonical_category FROM {VIEW} WHERE canonical_category LIKE 'Nest%%'",
    )
    assert {r[0] for r in rows} == {"Nest", "Nest-USA", "Nest-Canada"}


def test_crm_is_denied():
    with pytest.raises(psycopg.errors.InsufficientPrivilege):
        as_role("crm_marketing", f"SELECT count(*) FROM {VIEW}")
