import pandas as pd
import pytest

import fabric_control
from app.services.target_achievement import goal_text, detail_text, rows

NAMES = {
    "first_observed_buyers": "First Observed Buyers",
    "attributed_orders": "Attributed Orders",
    "attributed_gross_value": "Attributed Gross Value",
}


@pytest.fixture(autouse=True)
def terms(monkeypatch):
    monkeypatch.setattr(fabric_control, "term", lambda t: {"display_name": NAMES[t]})


def frame():
    # (campaign_id, metric, target, actual, achievement): 02 and 04 tie at 89.3% so campaign_id breaks it
    data = [
        ("CMP19_01", "attributed_gross_value", 25923.17, 28177.36, 1.087),
        ("CMP19_02", "attributed_orders", 495, 442, 0.893),
        ("CMP19_03", "first_observed_buyers", 40, 28, 0.7),
        ("CMP19_04", "attributed_gross_value", 32428.42, 28953.95, 0.893),
        ("CMP19_05", "attributed_orders", 267, 290, 1.086),
    ]
    return pd.DataFrame(
        [
            {
                "campaign_id": c,
                "campaign_name": f"Name {c}",
                "target_metric": m,
                "target_value": t,
                "actual": a,
                "achievement": r,
                "allocated_spend": 18897.68,
            }
            for c, m, t, a, r in data
        ]
    )


def test_goal_text():
    assert goal_text("first_observed_buyers", 40) == "Goal: 40 new buyers"
    assert goal_text("attributed_orders", 495) == "Goal: 495 orders"
    assert goal_text("attributed_gross_value", 32428.42) == "Goal: 32.4k in sales"


def test_detail_text_uses_canonical_name_and_no_currency():
    assert detail_text("first_observed_buyers", 28, 40, 18897.68) == "28 of 40 First Observed Buyers. Spent 18,898"


def test_rows_sorted_needs_attention_first():
    out = rows(frame())
    assert list(out.campaign_id) == ["CMP19_03", "CMP19_02", "CMP19_04", "CMP19_05", "CMP19_01"]
    assert out.set_index("campaign_id").goal["CMP19_03"] == "Goal: 40 new buyers"
    assert out.set_index("campaign_id").detail["CMP19_03"].startswith("28 of 40 First Observed Buyers")
