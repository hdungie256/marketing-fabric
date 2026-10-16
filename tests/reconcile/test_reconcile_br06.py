import os

import psycopg
import pytest

pytest.importorskip("pyspark")
from pipelines import io  # noqa: E402

VIEW = "mart_campaign_v.new_returning"
EXPECTED_SQL = """
WITH periods AS (
  SELECT * FROM VALUES
    ('FY2019', DATE'2019-01-01', DATE'2019-12-31'),
    ('2019-Q1', DATE'2019-01-01', DATE'2019-03-31'),
    ('2019-Q2', DATE'2019-04-01', DATE'2019-06-30'),
    ('2019-Q3', DATE'2019-07-01', DATE'2019-09-30'),
    ('2019-Q4', DATE'2019-10-01', DATE'2019-12-31')
  AS p(period_id, period_start, period_end)
),
names AS (SELECT campaign_id FROM campaigns UNION ALL SELECT 'ALL'),
facts AS (
  SELECT a.campaign_id, a.order_date, a.customer_id, c.first_observed_order_date
  FROM attribution a JOIN customers c ON c.customer_id = a.customer_id
),
scoped AS (
  SELECT * FROM facts UNION ALL SELECT 'ALL', order_date, customer_id, first_observed_order_date FROM facts
)
SELECT p.period_id, n.campaign_id,
       COUNT(DISTINCT s.customer_id) AS attributed_buyers,
       COUNT(DISTINCT CASE WHEN s.order_date = s.first_observed_order_date THEN s.customer_id END)
         AS first_observed_buyers
FROM periods p CROSS JOIN names n
LEFT JOIN scoped s ON s.campaign_id = n.campaign_id AND s.order_date BETWEEN p.period_start AND p.period_end
GROUP BY p.period_id, n.campaign_id
"""


def test_view_matches_independent_unified_sql():
    spark = io.get_spark()
    for name, dataset_id in [
        ("attribution", "unified/attribution"),
        ("customers", "unified/customers"),
        ("campaigns", "unified/campaigns"),
    ]:
        io.read_delta(dataset_id).createOrReplaceTempView(name)
    want = {
        (r.period_id, r.campaign_id): (r.attributed_buyers, r.first_observed_buyers)
        for r in spark.sql(EXPECTED_SQL).collect()
    }
    with psycopg.connect(os.environ["SERVING_DB_DSN"]) as conn, conn.transaction(force_rollback=True):
        conn.execute("SET LOCAL ROLE marketing_analyst")
        rows = conn.execute(f"SELECT period_id, campaign_id, attributed_buyers, first_observed_buyers FROM {VIEW}")
        got = {(p, c): (b, f) for p, c, b, f in rows.fetchall()}
    assert got == want
