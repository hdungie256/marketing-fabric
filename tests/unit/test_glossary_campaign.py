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
