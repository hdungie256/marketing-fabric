from datetime import UTC, datetime
from decimal import Decimal

import pandas as pd
import pytest
from streamlit.testing.v1 import AppTest

import fabric_control
from app.pages.finance import contribution
from app.shell import STATUS_COLORS
from app.shell.table import DENIED_TEXT
from fabric_control.glossary import load_terms

FRESH = datetime(2026, 10, 13, 7, 0, tzinfo=UTC)


def campaigns():
    return pd.DataFrame(
        [("CMP19_01", "Spring", Decimal("50.00"), Decimal("10.00"), Decimal("7.00"), Decimal("33.00"), 1)],
        columns=[
            "campaign_id", "campaign_name", "attributed_gross_value", "reference_cogs", "campaign_cost",
            "estimated_contribution", "skus_without_cost",
        ],
    ).assign(provenance="synthetic", _refreshed_at=FRESH)  # fmt: skip


def skus(denied: bool):
    cost = None if denied else Decimal("2.00")
    rows = [
        ("CMP19_01", "SKU1", "Pen", 5, Decimal("50.00"), cost, None if denied else Decimal("10.00"), True),
        ("CMP19_01", "SKU2", "Cap", 1, Decimal("20.00"), None, None, False),
    ]
    cols = ["campaign_id", "product_sku", "product_description", "quantity", "attributed_gross_value"]
    df = pd.DataFrame(rows, columns=[*cols, "estimated_unit_cost", "reference_cogs", "cost_available"])
    if denied:
        df = df.assign(estimated_unit_cost__denied=True, reference_cogs__denied=True)
    return df.assign(provenance="synthetic", _refreshed_at=FRESH)


ROLE = {"value": "UG04"}


class Source:
    def read(self, dataset_id):
        if dataset_id == contribution.CAMPAIGNS:
            return campaigns()
        return skus(denied=ROLE["value"] == "UG03")


def _script():
    from app.pages.finance.contribution import render
    from app.shell import session

    session.set_role("UG04")
    render()


@pytest.mark.parametrize("role,denied", [("UG04", False), ("UG03", True)])
def test_sku_cost_visible_to_finance_and_denied_for_manager(monkeypatch, role, denied):
    ROLE["value"] = role
    terms = load_terms()
    monkeypatch.setattr(fabric_control, "term", lambda term_id: terms.get(term_id))
    monkeypatch.setattr(fabric_control, "effective_matrix", lambda: [])
    monkeypatch.setattr(contribution, "current_source", lambda: Source())
    at = AppTest.from_function(_script).run()
    assert not at.exception, at.exception
    sku_table = at.dataframe[1].value
    assert (DENIED_TEXT in set(sku_table["reference_cogs"].astype(str))) is denied
    text = " ".join(m.value for m in at.markdown) + " ".join(c.value for c in at.caption)
    assert "Estimated Contribution" in text and "33" in text
    assert "1 SKUs have no reference cost" in text
    assert len(at.dataframe) == 3


def test_contribution_bars_are_sorted_around_a_zero_rule_with_a_loss_color(monkeypatch):
    terms = load_terms()
    monkeypatch.setattr(fabric_control, "term", lambda term_id: terms.get(term_id))
    loss = campaigns().assign(
        campaign_id="CMP19_04", campaign_name="Office", estimated_contribution=Decimal("-10283.85")
    )
    spec = contribution.contribution_bars(pd.concat([loss, campaigns()])).to_dict()
    bars, zero, gains, losses = spec["layer"]
    assert bars["encoding"]["y"]["sort"] == ["Spring · CMP19_01", "Office · CMP19_04"]
    scale = bars["encoding"]["color"]["scale"]
    assert dict(zip(scale["domain"], scale["range"], strict=True))["Negative"] == STATUS_COLORS["danger"]
    assert zero["mark"]["type"] == "rule" and spec["datasets"][zero["data"]["name"]] == [{"value": 0}]
    rows = spec["datasets"][bars["data"]["name"]]
    assert {r["label"]: r["sign"] for r in rows} == {"33": "Positive", "-10,284": "Negative"}
    assert [(layer["mark"]["align"], layer["transform"]) for layer in (gains, losses)] == [
        ("left", [{"filter": "datum.value >= 0"}]),
        ("right", [{"filter": "datum.value < 0"}]),
    ]


def test_page_charts_contribution_and_hides_provenance(monkeypatch):
    ROLE["value"] = "UG04"
    terms = load_terms()
    monkeypatch.setattr(fabric_control, "term", lambda term_id: terms.get(term_id))
    monkeypatch.setattr(fabric_control, "effective_matrix", lambda: [])
    monkeypatch.setattr(contribution, "current_source", lambda: Source())
    at = AppTest.from_function(_script).run()
    assert not at.exception, at.exception
    assert len(at.get("vega_lite_chart")) == 1
    assert "provenance" not in at.dataframe[0].value.columns


def test_contribution_metrics_show_refreshing(monkeypatch):
    terms = load_terms()
    monkeypatch.setattr(fabric_control, "term", lambda term_id: terms.get(term_id))
    monkeypatch.setattr(fabric_control, "effective_matrix", lambda: [])
    monkeypatch.setattr(contribution, "current_source", lambda: Source())
    monkeypatch.setattr(contribution, "current_in_flight", lambda campaigns: frozenset({contribution.CAMPAIGNS}))
    monkeypatch.setattr(contribution, "watch", lambda campaigns, shown: None)
    at = AppTest.from_function(_script).run()
    assert not at.exception, at.exception
    values = [m.value for m in at.markdown]
    assert " ".join(values).count("Refreshing…") == 2 and "33" in values
