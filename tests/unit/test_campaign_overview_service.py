from datetime import UTC, date, datetime
from decimal import Decimal

import pandas as pd
import pytest

from app.services import campaign_overview as svc

AT = datetime(2026, 10, 12, 7, 5, tzinfo=UTC)
PERIODS = [
    ("2019-Q2", "Q2 2019", date(2019, 4, 1), date(2019, 6, 30)),
    ("FY2019", "Jan–Dec 2019", date(2019, 1, 1), date(2019, 12, 31)),
    ("2019-Q1", "Q1 2019", date(2019, 1, 1), date(2019, 3, 31)),
]
CAMPAIGNS = [("CMP19_02", "Spring Nest"), ("ALL", "All campaigns"), ("CMP19_01", "New-year Apparel")]


def frame():
    rows = []
    for pid, label, start, end in PERIODS:
        for cid, name in CAMPAIGNS:
            orders = 0 if (pid, cid) == ("2019-Q2", "CMP19_01") else 10
            rows.append(
                {
                    "period_id": pid,
                    "period_label": label,
                    "period_start": start,
                    "period_end": end,
                    "campaign_id": cid,
                    "campaign_name": name,
                    "attributed_orders": orders,
                    "attributed_buyers": orders // 2,
                    "attributed_gross_value": Decimal(orders * 12),
                    "average_order_value": Decimal("12.00") if orders else None,
                    "provenance": "synthetic",
                    "_refreshed_at": AT,
                    "_run_id": "r",
                    "_source_version": "{}",
                }
            )
    return pd.DataFrame(rows)


class Source:
    def read(self, dataset_id):
        assert dataset_id == "mart_campaign.campaign_overview"
        return frame()


def test_load_casts_money_columns_to_float():
    df = svc.load(Source())
    assert df["attributed_gross_value"].dtype == "float64"
    assert df["average_order_value"].dtype == "float64"
    assert df["attributed_orders"].dtype == "int64"


def test_periods_start_with_full_year_then_quarters():
    assert svc.periods(svc.load(Source())) == [
        ("FY2019", "Jan–Dec 2019"),
        ("2019-Q1", "Q1 2019"),
        ("2019-Q2", "Q2 2019"),
    ]


def test_campaigns_start_with_all():
    assert svc.campaigns(svc.load(Source())) == [
        ("ALL", "All campaigns"),
        ("CMP19_01", "New-year Apparel"),
        ("CMP19_02", "Spring Nest"),
    ]


def test_select_all_returns_total_row_and_campaign_rows():
    kpi, rows = svc.select(svc.load(Source()), "FY2019", "ALL")
    assert kpi["campaign_id"] == "ALL"
    assert list(rows["campaign_id"]) == ["CMP19_01", "CMP19_02"]


def test_select_one_campaign_returns_only_it():
    kpi, rows = svc.select(svc.load(Source()), "2019-Q2", "CMP19_01")
    assert kpi["attributed_orders"] == 0
    assert list(rows["campaign_id"]) == ["CMP19_01"]


def test_select_missing_row_raises():
    with pytest.raises(KeyError, match="2019-Q3"):
        svc.select(svc.load(Source()), "2019-Q3", "ALL")


def test_gross_value_share_is_against_the_period_all_row():
    df = pd.DataFrame(
        {
            "period_id": ["FY2019"] * 3,
            "campaign_id": ["ALL", "CMP19_01", "CMP19_02"],
            "attributed_gross_value": [200.0, 50.0, 150.0],
        }
    )
    table = df[df["campaign_id"] != "ALL"]
    assert svc.gross_value_share(df, "FY2019", table).tolist() == [0.25, 0.75]
