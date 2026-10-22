"""Unified orders + RFM on Flink SQL in batch mode, same logic as the demo's Spark transforms (Story 9.1).

The segment CASE and the category map are generated from governance/ files, never hand-copied.
Usage: python -m benchmark.processing.flink_job <data_dir> <out_dir>
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

from benchmark.processing.common import AS_OF, CATEGORY_MAP, PARALLELISM, SEGMENTS, report


def literal(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


def condition(spec: dict) -> str:
    """SQL twin of rfm.transforms.condition: <dim>_min/_max/_eq/_in and `any` OR groups."""
    columns = {"r": "recency_score", "f": "frequency_score", "m": "monetary_score"}
    ops = {"min": ">=", "max": "<=", "eq": "="}
    parts = []
    for key, value in spec.items():
        if key == "any":
            parts.append("(" + " OR ".join(condition(option) for option in value) + ")")
            continue
        dim, _, op = key.partition("_")
        if op == "in":
            parts.append(f"{columns[dim]} IN ({', '.join(map(str, value))})")
        else:
            parts.append(f"{columns[dim]} {ops[op]} {value}")
    return " AND ".join(parts) or "TRUE"


def segment_case() -> str:
    whens = " ".join(f"WHEN {condition(s['when'])} THEN {literal(s['name'])}" for s in SEGMENTS[:-1])
    return f"CASE {whens} ELSE {literal(SEGMENTS[-1]['name'])} END"


def category_case() -> str:
    whens = " ".join(f"WHEN {literal(raw)} THEN {literal(canonical)}" for raw, canonical in CATEGORY_MAP.items())
    return f"CASE product_category {whens} ELSE product_category END" if CATEGORY_MAP else "product_category"


def statements(data: Path, out: Path) -> list[str]:
    def table(name: str, columns: str, path: Path) -> str:
        return f"CREATE TABLE {name} ({columns}) WITH ('connector'='filesystem', 'path'='{path}', 'format'='csv')"

    return [
        table(
            "lines",
            "customer_id BIGINT, transaction_id BIGINT, transaction_date_iso DATE, product_category STRING, "
            "quantity INT, avg_price DECIMAL(18,2), delivery_charges DECIMAL(18,2), provenance STRING",
            data / "lines.csv",
        ),  # fmt: skip
        table(
            "customers", "customer_id BIGINT, gender STRING, location STRING, tenure_months INT", data / "customers.csv"
        ),  # fmt: skip
        table(
            "orders_out",
            "order_key STRING, customer_id BIGINT, transaction_id BIGINT, order_date DATE, "
            "gross_value DECIMAL(38,2), shipping_fee DECIMAL(18,2), line_count INT",
            out / "orders",
        ),  # fmt: skip
        table(
            "rfm_out",
            "customer_id BIGINT, recency_days INT, recency_score INT, frequency_orders INT, "
            "frequency_score INT, monetary_value DECIMAL(38,2), monetary_score INT, segment STRING, "
            "categories STRING, gender STRING, location STRING, tenure_months INT",
            out / "rfm",
        ),  # fmt: skip
        """CREATE TEMPORARY VIEW orders AS
           SELECT CAST(customer_id AS STRING) || '|' || CAST(transaction_id AS STRING) AS order_key,
                  customer_id, transaction_id, MIN(transaction_date_iso) AS order_date,
                  SUM(quantity * avg_price) AS gross_value, MAX(delivery_charges) AS shipping_fee,
                  CAST(COUNT(*) AS INT) AS line_count
           FROM lines GROUP BY customer_id, transaction_id""",
        f"""CREATE TEMPORARY VIEW scored AS
            SELECT *,
              CAST(6 - NTILE(5) OVER (ORDER BY recency_days ASC, customer_id ASC) AS INT) AS recency_score,
              CAST(6 - NTILE(5) OVER (ORDER BY frequency_orders DESC, customer_id ASC) AS INT) AS frequency_score,
              CAST(6 - NTILE(5) OVER (ORDER BY monetary_value DESC, customer_id ASC) AS INT) AS monetary_score
            FROM (
              SELECT customer_id, CAST(COUNT(DISTINCT order_key) AS INT) AS frequency_orders,
                     SUM(gross_value) AS monetary_value,
                     TIMESTAMPDIFF(DAY, CAST(MAX(order_date) AS TIMESTAMP), TIMESTAMP '{AS_OF} 00:00:00')
                       AS recency_days
              FROM orders GROUP BY customer_id)""",
        f"""CREATE TEMPORARY VIEW categories AS
            SELECT customer_id, ARRAY_JOIN(ARRAY_SORT(ARRAY_AGG(DISTINCT {category_case()})), ',') AS categories
            FROM lines GROUP BY customer_id""",
    ]


def main(data: Path, out: Path) -> None:
    from pyflink.table import EnvironmentSettings, TableEnvironment

    env = TableEnvironment.create(EnvironmentSettings.in_batch_mode())
    env.get_config().set("parallelism.default", str(PARALLELISM))
    started = time.perf_counter()
    for statement in statements(data, out):
        env.execute_sql(statement)
    inserts = env.create_statement_set()
    inserts.add_insert_sql("INSERT OVERWRITE orders_out SELECT * FROM orders")
    inserts.add_insert_sql(f"""INSERT OVERWRITE rfm_out
        SELECT s.customer_id, s.recency_days, s.recency_score, s.frequency_orders, s.frequency_score,
               s.monetary_value, s.monetary_score, {segment_case()} AS segment, COALESCE(c.categories, ''),
               p.gender, p.location, p.tenure_months
        FROM scored s LEFT JOIN categories c ON s.customer_id = c.customer_id
                      LEFT JOIN customers p ON s.customer_id = p.customer_id""")
    inserts.execute().wait()
    report("flink", data, started, flink_version="2.2.1")


if __name__ == "__main__":
    main(Path(sys.argv[1]), Path(sys.argv[2]))
