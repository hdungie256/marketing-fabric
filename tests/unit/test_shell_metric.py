import pytest
from streamlit.testing.v1 import AppTest

import fabric_control
from app.shell.metric import NOTE_TEXT

TERMS = {
    "attributed_orders": {"display_name": "Attributed Orders", "notes": [], "synthetic": True},
    "attributed_gross_value": {
        "display_name": "Attributed Gross Value",
        "notes": ["currency_unverified", "attributed_not_incremental"],
        "synthetic": True,
    },
    "campaign_budget": {"display_name": "Campaign Budget", "notes": ["currency_unverified"], "synthetic": False},
    "bad_note": {"display_name": "Bad", "notes": ["made_up"], "synthetic": False},
}


@pytest.fixture(autouse=True)
def glossary(monkeypatch):
    monkeypatch.setattr(fabric_control, "term", lambda term_id: TERMS.get(term_id))


def _metric_script(cards):
    from datetime import UTC, datetime

    import streamlit as st

    from app.shell import metric
    from app.shell.page import footnotes

    freshness = datetime(2026, 10, 5, 7, 5, tzinfo=UTC)
    for term_id, value, kind in cards:
        if kind == "no-freshness":
            metric(term_id, value, None)
        else:
            metric(term_id, value, freshness, kind=kind)
    st.text("|".join(footnotes()))


def markdown(at):
    return [m.value for m in at.markdown]


def test_note_text_covers_every_glossary_note():
    assert set(NOTE_TEXT) == {
        "currency_unverified",
        "retrospective_target",
        "estimate_not_profit",
        "attributed_not_incremental",
        "first_in_observed_history",
    }


def test_metric_renders_label_value_and_badges(monkeypatch):
    monkeypatch.delenv("APP_TZ", raising=False)
    at = AppTest.from_function(_metric_script, args=([("attributed_orders", 1290, "count")],)).run()
    assert not at.exception
    assert "Attributed Orders" in markdown(at)
    assert "1,290" in markdown(at)
    assert ":green-badge[:material/check_circle: Refreshed 14:05]" in markdown(at)
    assert ":gray-badge[:material/science: Synthetic]" in markdown(at)


def test_non_synthetic_term_has_no_synthetic_badge():
    at = AppTest.from_function(_metric_script, args=([("campaign_budget", 5000.0, "money")],)).run()
    assert not any("Synthetic" in m for m in markdown(at))
    assert "5,000" in markdown(at)


def test_currency_note_goes_to_footnotes_once_and_other_notes_to_caption():
    cards = [("attributed_gross_value", 10.0, "money"), ("campaign_budget", 5.0, "money")]
    at = AppTest.from_function(_metric_script, args=(cards,)).run()
    assert at.text[0].value == NOTE_TEXT["currency_unverified"]
    assert NOTE_TEXT["attributed_not_incremental"] in [c.value for c in at.caption]


def test_missing_value_renders_dash():
    at = AppTest.from_function(_metric_script, args=([("attributed_orders", None, "count")],)).run()
    assert "—" in markdown(at)


@pytest.mark.parametrize(
    "card,message",
    [
        (("not_a_term", 1, "count"), "Unknown glossary term: not_a_term"),
        (("attributed_orders", 1, "no-freshness"), "attributed_orders: freshness is required"),
        (("attributed_orders", 1, "percent"), "kind must be one of"),
        (("bad_note", 1, "count"), "bad_note: unknown notes ['made_up']"),
    ],
)
def test_invalid_metric_calls_fail_loudly(card, message):
    at = AppTest.from_function(_metric_script, args=([card],)).run()
    assert message in at.exception[0].message


def test_same_term_twice_fails_with_duplicate_key():
    cards = [("attributed_orders", 1, "count"), ("attributed_orders", 2, "count")]
    at = AppTest.from_function(_metric_script, args=(cards,)).run()
    assert "metric-attributed_orders" in at.exception[0].message
