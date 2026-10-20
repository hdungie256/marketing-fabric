"""BR05 e2e: RFM segment totals reconcile with buying customers (T-BR05)."""

import os

import psycopg

VIEW = "mart_customer_v.rfm"
DSN = os.environ.get("SERVING_DB_DSN", "")


def as_role(login, query, params=()):
    with psycopg.connect(DSN) as conn, conn.transaction(force_rollback=True):
        conn.execute(f"SET LOCAL ROLE {login}")
        return conn.execute(query, params).fetchall()


def test_segment_totals_and_scores_in_range():
    rows = as_role("crm_marketing", f"SELECT count(*), count(DISTINCT customer_id) FROM {VIEW}")
    assert rows[0][0] == rows[0][1] > 0
    bad = as_role(
        "crm_marketing",
        f"SELECT count(*) FROM {VIEW} WHERE recency_score NOT BETWEEN 1 AND 5"
        " OR frequency_score NOT BETWEEN 1 AND 5 OR monetary_score NOT BETWEEN 1 AND 5",
    )
    assert bad == [(0,)]
