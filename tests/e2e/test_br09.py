"""BR09 e2e: win-back lists exactly (F = 5 or M = 5) and R = 1 (T-BR09)."""

import os

import psycopg

VIEW = "mart_customer_v.rfm"
DSN = os.environ.get("SERVING_DB_DSN", "")


def as_role(login, query, params=()):
    with psycopg.connect(DSN) as conn, conn.transaction(force_rollback=True):
        conn.execute(f"SET LOCAL ROLE {login}")
        return conn.execute(query, params).fetchall()


def test_win_back_predicate_is_exact():
    listed = as_role(
        "crm_marketing",
        f"SELECT customer_id FROM {VIEW} WHERE (frequency_score = 5 OR monetary_score = 5) AND recency_score = 1",
    )
    assert listed, "expected at least one lapsed high-value buyer in the sample"
    leaked = as_role(
        "crm_marketing",
        f"SELECT count(*) FROM {VIEW} WHERE NOT ((frequency_score = 5 OR monetary_score = 5)"
        " AND recency_score = 1) AND customer_id = ANY(%s)",
        [[r[0] for r in listed]],  # a list adapts to a Postgres array; customer_id is text in policy views
    )
    assert leaked == [(0,)]
