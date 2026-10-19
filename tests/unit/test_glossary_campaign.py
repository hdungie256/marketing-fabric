import pytest

import fabric_control
from app.shell import NOTE_TEXT

TERMS = ["attributed_orders", "attributed_buyers", "attributed_gross_value", "average_order_value"]


@pytest.mark.parametrize("term_id", TERMS)
def test_campaign_terms_link_overview_mart_with_known_notes(term_id):
    t = fabric_control.term(term_id)
    assert t["dataset_id"] == "mart_campaign.campaign_overview"
    assert t["column"] == term_id
    assert set(t["notes"]) <= set(NOTE_TEXT)
    assert t["synthetic"] is True


def test_money_terms_carry_currency_note():
    assert "currency_unverified" in fabric_control.term("attributed_gross_value")["notes"]
    assert "currency_unverified" in fabric_control.term("average_order_value")["notes"]


def test_quantity_sold_term_links_product_sales_mart():
    t = fabric_control.term("quantity_sold")
    assert t["dataset_id"] == "mart_campaign.product_sales"
    assert t["column"] == "quantity"


def test_returning_buyers_term_links_new_returning_mart():
    t = fabric_control.term("returning_buyers")
    assert (t["dataset_id"], t["column"]) == ("mart_campaign.new_returning", "returning_buyers")


def test_first_observed_buyers_carries_r9_note():
    assert fabric_control.term("first_observed_buyers")["notes"] == ["first_in_observed_history"]


def test_new_vs_returning_terms_state_the_attribution_scope():
    for term_id in ("first_observed_buyers", "returning_buyers"):
        limitations = " ".join(fabric_control.term(term_id)["limitations"])
        assert "first observed order is attributed" in limitations, term_id


def test_target_achievement_term_links_target_mart():
    t = fabric_control.term("target_achievement")
    assert t["display_name"] == "Target Achievement"
    assert t["dataset_id"] == "mart_campaign.target_achievement"
    assert t["column"] == "achievement"
    assert "retrospective_target" in t["notes"]
    assert "R14" in t["rules"]
