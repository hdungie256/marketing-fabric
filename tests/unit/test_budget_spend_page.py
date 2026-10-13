from datetime import UTC, date, datetime
from decimal import Decimal

import pandas as pd
import pytest
from streamlit.testing.v1 import AppTest

import fabric_control
from app.pages.finance import budget_spend
from app.pages.finance.budget_spend import by_campaign, stack, summarize
from fabric_control.glossary import load_terms

FRESH = datetime(2026, 10, 13, 7, 0, tzinfo=UTC)
D1, D2, D3 = date(2019, 1, 15), date(2019, 1, 16), date(2019, 1, 17)


def budget_rows():
    rows = [
        ("CMP19_01", D1, "Spring", Decimal("1000"), Decimal("10.00"), 2, Decimal("40.00")),
        ("CMP19_01", D2, "Spring", Decimal("1000"), Decimal("30.00"), 2, Decimal("100.00")),
        ("CMP19_02", D3, "Summer", Decimal("500"), Decimal("0.00"), 0, Decimal("0.00")),
    ]
    cols = ["campaign_id", "date", "campaign_name", "campaign_budget", "allocated", "attributed_orders"]
    df = pd.DataFrame(rows, columns=[*cols, "attributed_gross_value"])
    return df.assign(channel="Paid Search", provenance="synthetic", _refreshed_at=FRESH)


def recon_rows():
    rows = [
        (D1, Decimal("100.00"), Decimal("10.00"), Decimal("90.00")),
        (D2, Decimal("30.00"), Decimal("30.00"), Decimal("0.00")),
    ]
    df = pd.DataFrame(rows, columns=["date", "online_spend", "allocated", "unallocated"])
    return df.assign(offline_spend=Decimal("4500"), provenance="synthetic", _refreshed_at=FRESH)


def test_summary_counts_budget_once_per_campaign_and_uses_ratio_of_sums():
    values = summarize(budget_rows(), recon_rows())
    assert values["campaign_budget"] == Decimal("1500")
    assert values["allocated_spend"] == Decimal("40.00")
    assert values["unallocated_spend"] == Decimal("90.00")
    assert values["attributed_value_per_spend_ratio"] == Decimal("3.5")
    assert values["cost_per_attributed_order"] == Decimal("10")


def test_campaign_without_spend_or_orders_has_no_ratio():
    summer = by_campaign(budget_rows()).set_index("campaign_id").loc["CMP19_02"]
    assert summer["value_per_spend"] is None and summer["cost_per_order"] is None


def test_stack_has_one_bar_segment_per_day_and_kind():
    data = stack(recon_rows())
    assert sorted(data["segment"].unique()) == ["Allocated", "Unallocated"] and len(data) == 4


def test_page_terms_exist_in_glossary():
    assert set(summarize(budget_rows(), recon_rows())) <= set(load_terms())


class Source:
    def read(self, dataset_id):
        return {"mart_finance.budget_daily": budget_rows(), "mart_shared.spend_reconciliation": recon_rows()}[
            dataset_id
        ]


def _script():
    from app.pages.finance.budget_spend import render
    from app.shell import session

    session.set_role("UG04")
    render()


@pytest.mark.parametrize("table_view", [False, True])
def test_page_renders_metrics_chart_and_table(monkeypatch, table_view):
    terms = load_terms()
    monkeypatch.setattr(fabric_control, "term", lambda term_id: terms.get(term_id))
    monkeypatch.setattr(fabric_control, "effective_matrix", lambda: [])
    monkeypatch.setattr(budget_spend, "current_source", lambda: Source())
    at = AppTest.from_function(_script).run()
    if table_view:
        at.toggle(key="budget_spend_table_view").set_value(True).run()
    assert not at.exception, at.exception
    text = " ".join(m.value for m in at.markdown)
    assert "Attributed Value / Spend Ratio" in text and "3.50×" in text
    assert len(at.dataframe) == (2 if table_view else 1)
