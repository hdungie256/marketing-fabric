"""Build benchmark inputs ×1/×10/×100 from the sample workbooks (Story 9.1).

Copy k shifts both customer_id and transaction_id by k × OFFSET, so every copy adds new customers and
orders and order_key stays unique. Both engines read the same CSV files.
"""

from __future__ import annotations

import csv
import sys
from pathlib import Path

import openpyxl

ROOT = Path(__file__).resolve().parents[2]
SALES = ROOT / "sources" / "data" / "01_Sales_Operational.xlsx"
CRM = ROOT / "sources" / "data" / "02_CRM_Customers.xlsx"
OFFSET = 10_000_000
LINE_COLUMNS = [
    "customer_id",
    "transaction_id",
    "transaction_date_iso",
    "product_category",
    "quantity",
    "avg_price",
    "delivery_charges",
    "provenance",
]
CUSTOMER_COLUMNS = ["customer_id", "gender", "location", "tenure_months"]


def rows(path: Path, sheet: int = 0) -> tuple[list[str], list[tuple]]:
    ws = openpyxl.load_workbook(path, read_only=True, data_only=True).worksheets[sheet]
    it = ws.iter_rows(values_only=True)
    return list(next(it)), list(it)


def build(out: Path, scale: int) -> None:
    head, sales = rows(SALES)
    i = {name: head.index(name) for name in head}
    chead, customers = rows(CRM)
    c = {name: chead.index(name) for name in chead}
    out.mkdir(parents=True, exist_ok=True)
    with (out / "lines.csv").open("w", newline="") as f:
        w = csv.writer(f)
        for k in range(scale):
            for r in sales:
                w.writerow(
                    [
                        r[i["CustomerID"]] + k * OFFSET,
                        r[i["Transaction_ID"]] + k * OFFSET,
                        str(r[i["Transaction_Date_ISO"]])[:10],
                        r[i["Product_Category"]],
                        r[i["Quantity"]],
                        f"{r[i['Avg_Price']]:.2f}",
                        f"{r[i['Delivery_Charges']]:.2f}",
                        "original",
                    ]
                )
    with (out / "customers.csv").open("w", newline="") as f:
        w = csv.writer(f)
        for k in range(scale):
            for r in customers:
                w.writerow([r[c["CustomerID"]] + k * OFFSET, r[c["Gender"]], r[c["Location"]], r[c["Tenure_Months"]]])


if __name__ == "__main__":
    base = Path(sys.argv[1])
    for scale in map(int, sys.argv[2:] or ["1", "10", "100"]):
        build(base / f"x{scale}", scale)
        print(f"x{scale}: {sum(1 for _ in (base / f'x{scale}' / 'lines.csv').open())} lines")
