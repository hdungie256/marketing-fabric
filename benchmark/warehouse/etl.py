"""Traditional warehouse baseline (Story 9.3): load the source workbooks into one Postgres database and rebuild
BR01/BR10 tables with plain SQL. Every run is a full batch: drop, load, transform.

Usage: python -m benchmark.warehouse.etl [--spend CAMPAIGN DAY VALUE]
--spend overrides one Campaign_Spend value as if the source had been edited (BR16 scenario).
"""

from __future__ import annotations

import argparse
import os
import time
from datetime import datetime
from decimal import Decimal
from pathlib import Path

import openpyxl
import psycopg

from benchmark.processing.common import report

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "sources" / "data"
TABLES = {
    "sales_lines": (
        "01_Sales_Operational",
        None,
        "customer_id bigint, transaction_id bigint, transaction_date date, quantity int, avg_price numeric(18,2)",
        lambda r: (r["CustomerID"], r["Transaction_ID"], r["Transaction_Date_ISO"], r["Quantity"], r["Avg_Price"]),
    ),
    "campaigns": (
        "03_Marketing_Campaigns",
        "Campaigns",
        "campaign_id text, campaign_name text, budget numeric(18,2)",
        lambda r: (r["Campaign_ID"], r["Campaign_Name"], r["Budget"]),
    ),
    "attribution": (
        "03_Marketing_Campaigns",
        "Attribution",
        "campaign_id text, customer_id bigint, transaction_id bigint",
        lambda r: (r["Campaign_ID"], r["CustomerID"], r["Transaction_ID"]),
    ),
    "campaign_spend": (
        "04_Finance_Costs",
        "Campaign_Spend",
        "campaign_id text, spend_date date, allocated_online_spend numeric(18,2)",
        lambda r: (r["Campaign_ID"], r["Date_ISO"], r["Allocated_Online_Spend"]),
    ),
    "daily_spend": (
        "04_Finance_Costs",
        "Daily_Spend",
        "spend_date date, online_spend numeric(18,2)",
        lambda r: (datetime.strptime(r["Date"], "%m/%d/%Y").date(), r["Online_Spend"]),
    ),
}


def sheet(book: str, name: str | None) -> list[dict]:
    wb = openpyxl.load_workbook(DATA / f"{book}.xlsx", read_only=True, data_only=True)
    ws = wb[name] if name else wb.worksheets[0]
    rows = ws.iter_rows(values_only=True)
    head = next(rows)
    return [dict(zip(head, r, strict=True)) for r in rows]


def load(conn, spend: tuple[str, str, str] | None) -> None:
    conn.execute("DROP SCHEMA IF EXISTS wh CASCADE")
    conn.execute("CREATE SCHEMA wh")
    for table, (book, name, columns, pick) in TABLES.items():
        conn.execute(f"CREATE TABLE wh.{table} ({columns})")
        values = [pick(r) for r in sheet(book, name)]
        if spend and table == "campaign_spend":
            campaign, day, value = spend
            values = [(c, d, Decimal(value) if (c, str(d)[:10]) == (campaign, day) else v) for c, d, v in values]
        with conn.cursor().copy(f"COPY wh.{table} FROM STDIN") as copy:
            for row in values:
                copy.write_row(row)


def main(spend: tuple[str, str, str] | None) -> None:
    started = time.perf_counter()
    with psycopg.connect(os.environ["WAREHOUSE_DSN"]) as conn:
        load(conn, spend)
        loaded = time.perf_counter()
        conn.execute((Path(__file__).parent / "marts.sql").read_text())
        conn.commit()
    report(
        "warehouse",
        Path("warehouse"),
        started,
        load_s=round(loaded - started, 2),
        transform_s=round(time.perf_counter() - loaded, 2),
        spend_override=spend,
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--spend", nargs=3, metavar=("CAMPAIGN", "DAY", "VALUE"))
    main(tuple(parser.parse_args().spend) if parser.parse_args().spend else None)
