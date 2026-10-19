import re
from datetime import UTC, datetime

import pandas as pd
import pytest
from streamlit.testing.v1 import AppTest

import fabric_control
from app.pages.campaign import targets

AT = datetime(2026, 10, 19, 7, 5, tzinfo=UTC)
NAMES = {
    "first_observed_buyers": "First Observed Buyers",
    "attributed_orders": "Attributed Orders",
    "attributed_gross_value": "Attributed Gross Value",
    "target_achievement": "Target Achievement",
    "allocated_spend": "Allocated Spend",
}
STALE_DATASET = "mart_shared.campaign_spend_allocated"
SUBTITLE = "How far each campaign got toward its own goal."
FOOTNOTE = "Stop below 70%, Continue from 100%. Goals were set after the fact for this demo."


def frame():
    data = [
        ("CMP19_01", "New-year Apparel", "attributed_gross_value", 25923.17, 28177.36, 1.086962, "continue"),
        ("CMP19_02", "Spring Nest", "attributed_orders", 495, 442, 0.892929, "adjust"),
        ("CMP19_03", "Summer Drinkware", "first_observed_buyers", 40, 28, 0.7, "adjust"),
        ("CMP19_04", "Back-to-work Office", "attributed_gross_value", 32428.42, 28953.95, 0.892853, "adjust"),
        ("CMP19_05", "Holiday Nest", "attributed_orders", 267, 290, 1.086142, "continue"),
    ]
    return pd.DataFrame(
        [
            {
                "campaign_id": c,
                "campaign_name": n,
                "target_metric": m,
                "target_value": t,
                "evaluation_from": "2019-01-01",
                "evaluation_through": "2019-12-31",
                "actual": a,
                "achievement": r,
                "allocated_spend": 18897.68,
                "recommendation": rec,
                "provenance": "synthetic",
                "_refreshed_at": AT,
                "_run_id": "r",
                "_source_version": "{}",
            }
            for c, n, m, t, a, r, rec in data
        ]
    )


class Source:
    def read(self, dataset_id):
        return frame()


@pytest.fixture(autouse=True)
def stubs(monkeypatch):
    monkeypatch.setattr(
        fabric_control,
        "term",
        lambda t: {"display_name": NAMES[t], "notes": [], "synthetic": True} if t in NAMES else None,
    )
    monkeypatch.setattr(fabric_control, "record_timing", lambda page, ms: None)
    monkeypatch.setattr(fabric_control, "status", lambda d: {"stale": False, "datasets": []})
    monkeypatch.setattr(targets, "current_source", lambda: Source())


def _script():
    from app.pages.campaign import targets
    from app.shell import PageSpec, session
    from app.shell.page import wrap

    session.set_role("UG03")
    wrap(PageSpec("targets", "Targets", "Campaigns", targets.render, frozenset({"UG03"})))()


def text(at):
    return [*(m.value for m in at.markdown), *(c.value for c in at.caption), *(t.value for t in at.title)]


def chips(at):
    return re.findall(r"-badge\[:material/\w+: (Continue|Adjust|Stop)\]", " ".join(m.value for m in at.markdown))


def test_ruler_rows_and_chips():
    at = AppTest.from_function(_script).run()
    assert not at.exception
    assert not at.error
    shown = text(at)
    assert "Targets" in shown and SUBTITLE in shown and FOOTNOTE in shown
    assert chips(at) == ["Adjust", "Adjust", "Adjust", "Continue", "Continue"]
    assert any("Synthetic" in t for t in shown)


def test_table_view_has_cost_and_canonical_names():
    at = AppTest.from_function(_script).run()
    at.toggle(key="targets_table_view").set_value(True).run()
    assert not at.exception
    columns = list(at.dataframe[0].value.columns)
    assert "Allocated Spend" in columns and "Target Achievement" in columns


def test_stale_keeps_recommendation(monkeypatch):
    monkeypatch.setattr(fabric_control, "status", lambda d: {"stale": True, "datasets": [STALE_DATASET]})
    at = AppTest.from_function(_script).run()
    assert not at.exception
    assert any(STALE_DATASET in w.value for w in at.warning)
    assert len(chips(at)) == 5
    assert sum("Using previous version" in m.value for m in at.markdown) == 5
