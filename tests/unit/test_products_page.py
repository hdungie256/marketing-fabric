from datetime import UTC, date, datetime

import pandas as pd
import pytest
from streamlit.testing.v1 import AppTest

import fabric_control
from app.pages.campaign import products

AT = datetime(2026, 10, 16, 7, 5, tzinfo=UTC)
TERMS = {
    "gross_value": ("Gross Value", ["currency_unverified"]),
    "quantity_sold": ("Quantity Sold", ["attributed_not_incremental"]),
}


def frame():
    rows = []
    for month, cid, name, sku, cat, qty, gross in [
        (date(2019, 1, 1), "ALL", "All campaigns", "SKU-A", "Apparel", 5, 500.0),
        (date(2019, 1, 1), "ALL", "All campaigns", "SKU-N", "Nest", 2, 200.0),
        (date(2019, 2, 1), "ALL", "All campaigns", "SKU-US", "Nest-USA", 3, 300.0),
        (date(2019, 3, 1), "ALL", "All campaigns", "SKU-CA", "Nest-Canada", 4, 400.0),
        (date(2019, 1, 1), "CMP19_01", "New-year Apparel", "SKU-A", "Apparel", 5, 500.0),
        (date(2019, 7, 1), "CMP19_03", "Summer Drinkware", "SKU-D", "Drinkware", 1, 10.0),
    ]:
        rows.append(
            {
                "month": month,
                "campaign_id": cid,
                "campaign_name": name,
                "product_sku": sku,
                "product_description": sku.lower(),
                "canonical_category": cat,
                "quantity": qty,
                "gross_value": gross,
                "provenance": "synthetic",
                "_refreshed_at": AT,
                "_run_id": "r",
                "_source_version": "{}",
            }
        )
    return pd.DataFrame(rows)


class Source:
    def read(self, dataset_id):
        return frame()


@pytest.fixture(autouse=True)
def stubs(monkeypatch):
    monkeypatch.setattr(
        fabric_control,
        "term",
        lambda t: {"display_name": TERMS[t][0], "notes": TERMS[t][1], "synthetic": True} if t in TERMS else None,
    )
    monkeypatch.setattr(fabric_control, "record_timing", lambda page, ms: None)
    monkeypatch.setattr(products, "current_source", lambda: Source())


def _script():
    from app.pages.campaign import products
    from app.shell import PageSpec, session
    from app.shell.page import wrap

    session.set_role("UG01")
    wrap(PageSpec("products_categories", "Products & Categories", "Campaigns", products.render, frozenset({"UG01"})))()


def test_default_shows_top_skus_categories_and_trend():
    at = AppTest.from_function(_script).run()
    assert not at.exception
    assert at.selectbox(key="_filter_products_categories_period").value == "FY2019"
    at.toggle(key="products_top_skus_table_view")
    at.toggle(key="products_trend_table_view")
    categories = at.dataframe[0].value
    assert {"Nest", "Nest-USA", "Nest-Canada"} <= set(categories.iloc[:, 0])
    assert len(at.dataframe) == 1


def test_campaign_without_sales_shows_empty_state():
    at = AppTest.from_function(_script).run()
    at.selectbox(key="_filter_products_categories_period").set_value("2019-Q1").run()
    at.selectbox(key="_filter_products_categories_campaign").set_value("CMP19_03").run()
    assert not at.exception
    assert "No attributed sales for CMP19_03 in this period." in " ".join(m.value for m in at.markdown)
    assert "Clear the Campaign filter to see all." in [c.value for c in at.caption]
    assert not at.dataframe


def test_all_campaigns_discloses_unattributed_sales():
    at = AppTest.from_function(_script).run()
    assert "Includes sales not attributed to any campaign." in [c.value for c in at.caption]
    at.selectbox(key="_filter_products_categories_campaign").set_value("CMP19_01").run()
    assert "Includes sales not attributed to any campaign." not in [c.value for c in at.caption]
