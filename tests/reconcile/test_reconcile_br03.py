import os
from decimal import Decimal

import psycopg
import pytest

pytest.importorskip("pyspark")
from pipelines import io  # noqa: E402

VIEW = "mart_campaign_v.product_sales"
OVERVIEW = "mart_campaign_v.campaign_overview"
TOLERANCE = Decimal("0.01")


def as_analyst(query):
    with psycopg.connect(os.environ["SERVING_DB_DSN"]) as conn, conn.transaction(force_rollback=True):
        conn.execute("SET LOCAL ROLE marketing_analyst")
        return conn.execute(query).fetchall()


def test_campaign_gross_equals_overview():
    got = as_analyst(
        f"""
        SELECT o.period_id, o.campaign_id, o.attributed_gross_value, COALESCE(SUM(s.gross_value), 0)
        FROM {OVERVIEW} o
        LEFT JOIN {VIEW} s ON s.campaign_id = o.campaign_id AND s.month BETWEEN o.period_start AND o.period_end
        WHERE o.campaign_id <> 'ALL'
        GROUP BY o.period_id, o.campaign_id, o.attributed_gross_value
        """
    )
    assert got
    for period, campaign, overview_gross, sales_gross in got:
        assert abs(overview_gross - sales_gross) <= TOLERANCE, (period, campaign)


def test_all_rows_equal_order_lines():
    io.read_delta("unified/order_lines").createOrReplaceTempView("order_lines")
    want = {
        r.month: r.gross
        for r in io.get_spark()
        .sql(
            "SELECT trunc(transaction_date_iso, 'month') AS month, SUM(line_gross_value) AS gross "
            "FROM order_lines GROUP BY 1"
        )
        .collect()
    }
    got = dict(as_analyst(f"SELECT month, SUM(gross_value) FROM {VIEW} WHERE campaign_id = 'ALL' GROUP BY month"))
    assert set(got) == set(want)
    for month, gross in want.items():
        assert abs(got[month] - gross) <= TOLERANCE, month
