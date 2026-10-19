import os

import psycopg
import pytest

VIEW = "mart_campaign_v.target_achievement"
DSN = os.environ.get("SERVING_DB_DSN", "")


def as_role(login, query, *params):
    with psycopg.connect(DSN) as conn, conn.transaction(force_rollback=True):
        conn.execute(f"SET LOCAL ROLE {login}")
        return conn.execute(query, params).fetchall()


def test_every_recommendation_matches_fr31():
    rows = as_role(
        "marketing_manager",
        f"SELECT count(*) FROM {VIEW} WHERE recommendation <> CASE WHEN achievement >= 1 THEN 'continue' "
        "WHEN achievement >= 0.7 THEN 'adjust' ELSE 'stop' END",
    )
    assert rows == [(0,)]


def test_five_campaigns_each_with_own_target():
    rows = as_role("marketing_manager", f"SELECT target_metric FROM {VIEW}")
    assert len(rows) == 5
    assert {r[0] for r in rows} == {"attributed_gross_value", "attributed_orders", "first_observed_buyers"}


def test_demo_climax_summer_drinkware_on_the_line():
    rows = as_role(
        "marketing_manager",
        f"SELECT actual, target_value, achievement, recommendation FROM {VIEW} WHERE campaign_id = 'CMP19_03'",
    )
    assert [(float(a), float(t), float(r), rec) for a, t, r, rec in rows] == [(28.0, 40.0, 0.7, "adjust")]


def test_other_roles_denied():
    with pytest.raises(psycopg.errors.InsufficientPrivilege):
        as_role("marketing_analyst", f"SELECT 1 FROM {VIEW}")
