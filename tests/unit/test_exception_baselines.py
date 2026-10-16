"""Exception baselines pinned to the source workbooks (Story 3.3, FR-8, AC02).

Replicates the detection rules in pandas over sources/data so a data change
fails fast in CI without a live stack. The Spark jobs must reproduce these
exact marks: 1,319 shared codes, 400 mismatch lines (126 Used).
"""

from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
SALES = ROOT / "sources" / "data" / "01_Sales_Operational.xlsx"
CAMPAIGNS = ROOT / "sources" / "data" / "03_Marketing_Campaigns.xlsx"


def test_workbook_marks_match_baselines():
    sales = pd.read_excel(SALES, sheet_name="Sales_Lines")
    plan = pd.read_excel(CAMPAIGNS, sheet_name="Coupon_Plan")
    assert len(sales) == 52924
    shared = sales.groupby("Transaction_ID")["CustomerID"].nunique()
    assert int((shared > 1).sum()) == 1319
    normalized = sales["Product_Category"].replace({"Notebooks": "Notebooks & Journals"})
    mismatch = sales[~normalized.isin(set(plan["Product_Category"].unique()))]
    assert len(mismatch) == 400
    assert int((mismatch["Coupon_Status"] == "Used").sum()) == 126
    assert mismatch["Product_Category"].value_counts().to_dict() == {
        "Fun": 160,
        "Google": 105,
        "Backpacks": 89,
        "More Bags": 46,
    }
