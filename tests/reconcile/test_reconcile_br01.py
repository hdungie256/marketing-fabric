import os
from decimal import Decimal

import psycopg
import pytest

pytest.importorskip("pyspark")
from pipelines import io  # noqa: E402

VIEW = "mart_campaign_v.campaign_overview"
EXPECTED_SQL = """
WITH periods AS (
  SELECT * FROM VALUES
    ('FY2019', 'Jan–Dec 2019', DATE'2019-01-01', DATE'2019-12-31'),
    ('2019-Q1', 'Q1 2019', DATE'2019-01-01', DATE'2019-03-31'),
    ('2019-Q2', 'Q2 2019', DATE'2019-04-01', DATE'2019-06-30'),
    ('2019-Q3', 'Q3 2019', DATE'2019-07-01', DATE'2019-09-30'),
    ('2019-Q4', 'Q4 2019', DATE'2019-10-01', DATE'2019-12-31')
  AS p(period_id, period_label, period_start, period_end)
),
names AS (
  SELECT campaign_id, campaign_name FROM campaigns UNION ALL SELECT 'ALL', 'All campaigns'
),
facts AS (
  SELECT a.campaign_id, a.order_date, a.customer_id, a.order_key, CAST(o.gross_value AS DECIMAL(18,2)) AS gross_value
  FROM attribution a JOIN orders o ON o.order_key = a.order_key
),
scoped AS (
  SELECT * FROM facts
  UNION ALL SELECT 'ALL', order_date, customer_id, order_key, gross_value FROM facts
)
SELECT p.period_id, p.period_label, p.period_start, p.period_end, n.campaign_id, n.campaign_name,
       COUNT(s.order_key) AS attributed_orders,
       COUNT(DISTINCT s.customer_id) AS attributed_buyers,
       CAST(COALESCE(SUM(s.gross_value), 0) AS DECIMAL(18,2)) AS attributed_gross_value
FROM periods p CROSS JOIN names n
LEFT JOIN scoped s ON s.campaign_id = n.campaign_id AND s.order_date BETWEEN p.period_start AND p.period_end
GROUP BY p.period_id, p.period_label, p.period_start, p.period_end, n.campaign_id, n.campaign_name
"""


def expected() -> dict:
    spark = io.get_spark()
    for name, dataset_id in [("attribution", "unified/attribution"), ("orders", "unified/orders"), ("campaigns", "unified/campaigns")]:
        io.read_delta(dataset_id).createOrReplaceTempView(name)
    out = {}
    for r in spark.sql(EXPECTED_SQL).collect():
        d = r.asDict()
        d["average_order_value"] = (
            (d["attributed_gross_value"] / d["attributed_orders"]).quantize(Decimal("0.01")) if d["attributed_orders"] else None
        )
        d["provenance"] = "synthetic"
        out[(d["period_id"], d["campaign_id"])] = d
    return out


def actual() -> dict:
    with psycopg.connect(os.environ["SERVING_DB_DSN"]) as conn, conn.transaction(force_rollback=True):
        conn.execute("SET LOCAL ROLE marketing_analyst")
        cursor = conn.execute(f"SELECT * FROM {VIEW}")
        names = [c.name for c in cursor.description]
        rows = [dict(zip(names, r, strict=True)) for r in cursor.fetchall()]
    return {(r["period_id"], r["campaign_id"]): {k: v for k, v in r.items() if not k.startswith("_")} for r in rows}


def test_view_matches_independent_unified_sql():
    want, got = expected(), actual()
    assert set(got) == set(want)
    for key, row in want.items():
        for column, value in row.items():
            if isinstance(value, Decimal) and got[key][column] is not None:
                assert abs(got[key][column] - value) <= Decimal("0.01"), (key, column)
            else:
                assert got[key][column] == value, (key, column)
    assert got[("FY2019", "ALL")]["attributed_orders"] == 1290
