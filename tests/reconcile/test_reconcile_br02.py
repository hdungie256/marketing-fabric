import os

import psycopg

COMPARISON = "mart_campaign_v.comparison"
OVERVIEW = "mart_campaign_v.campaign_overview"
JOIN = f"""
FROM {COMPARISON} c JOIN {OVERVIEW} o ON o.period_id = c.period_id AND o.campaign_id = c.group_id
WHERE c.compare_by = 'campaign'
"""


def as_analyst(query):
    with psycopg.connect(os.environ["SERVING_DB_DSN"]) as conn, conn.transaction(force_rollback=True):
        conn.execute("SET LOCAL ROLE marketing_analyst")
        return conn.execute(query).fetchall()


def test_campaign_rows_equal_overview():
    joined = as_analyst(f"SELECT count(*) {JOIN}")
    assert joined == [(5 * 5,)]
    mismatched = as_analyst(
        f"""SELECT count(*) {JOIN}
        AND ((c.attributed_orders, c.attributed_buyers, c.attributed_gross_value)
            IS DISTINCT FROM (o.attributed_orders, o.attributed_buyers, o.attributed_gross_value)
            OR c.average_order_value IS DISTINCT FROM o.average_order_value)"""
    )
    assert mismatched == [(0,)]


def test_channel_orders_sum_campaigns():
    rows = as_analyst(
        f"""SELECT period_id, compare_by, sum(attributed_orders) FROM {COMPARISON}
        GROUP BY period_id, compare_by"""
    )
    by_period = {}
    for period, kind, total in rows:
        by_period.setdefault(period, {})[kind] = total
    assert by_period and all(v["campaign"] == v["channel"] for v in by_period.values())
