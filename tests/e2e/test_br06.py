import os

import psycopg
import pytest

VIEW = "mart_campaign_v.new_returning"
DSN = os.environ.get("SERVING_DB_DSN", "")


def as_role(login, query, *params):
    with psycopg.connect(DSN) as conn, conn.transaction(force_rollback=True):
        conn.execute(f"SET LOCAL ROLE {login}")
        return conn.execute(query, params).fetchall()


@pytest.mark.parametrize("login", ["marketing_analyst", "crm_marketing"])
def test_identity_for_analyst_and_crm(login):
    rows = as_role(
        login, f"SELECT count(*) FROM {VIEW} WHERE first_observed_buyers + returning_buyers <> attributed_buyers"
    )
    assert rows == [(0,)]


def test_all_buyers_equal_br01():
    rows = as_role(
        "marketing_analyst",
        f"SELECT attributed_buyers FROM {VIEW} WHERE period_id = 'FY2019' AND campaign_id = 'ALL'",
    )
    assert rows == [(456,)]
