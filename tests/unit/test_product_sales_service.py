from datetime import date

import pandas as pd

from app.services import product_sales as svc


def frame(rows):
    cols = ["month", "campaign_id", "campaign_name", "product_sku", "product_description", "canonical_category"]
    df = pd.DataFrame(rows, columns=[*cols, "quantity", "gross_value"])
    return df.assign(gross_value=df["gross_value"].astype("float64"))


ROWS = [
    (date(2019, 1, 1), "ALL", "All campaigns", "SKU-A", "Shirt", "Apparel", 1, 500.0),
    (date(2019, 2, 1), "ALL", "All campaigns", "SKU-B", "Mug", "Drinkware", 90, 100.0),
    (date(2019, 4, 1), "ALL", "All campaigns", "SKU-A", "Shirt", "Apparel", 1, 50.0),
    (date(2019, 2, 1), "CMP19_01", "New-year Apparel", "SKU-A", "Shirt", "Apparel", 1, 5.0),
]


def test_select_keeps_months_in_quarter():
    rows = svc.select(frame(ROWS), "2019-Q1", "ALL")
    assert sorted(rows["month"]) == [date(2019, 1, 1), date(2019, 2, 1)]


def test_select_filters_campaign():
    assert svc.select(frame(ROWS), "FY2019", "CMP19_01")["gross_value"].tolist() == [5.0]


def test_period_options_fy_then_quarters():
    options = svc.period_options(frame(ROWS))
    assert options[0] == ("FY2019", "Jan–Dec 2019") and len(options) == 5


def test_top_skus_rank_by_quantity_differs_from_gross():
    rows = frame(ROWS)
    assert svc.top_skus(rows, "gross_value")["product_sku"].tolist()[0] == "SKU-A"
    assert svc.top_skus(rows, "quantity")["product_sku"].tolist()[0] == "SKU-B"


def test_top_skus_sums_across_months_and_limits_n():
    top = svc.top_skus(frame(ROWS), "gross_value", n=1)
    assert len(top) == 1 and top["gross_value"].iloc[0] == 555.0


def test_trend_limits_to_top_four_categories():
    rows = frame(
        [(date(2019, 1, 1), "ALL", "All campaigns", f"S{i}", "d", f"Cat{i}", 1, float(i + 1)) for i in range(6)]
    )
    assert set(svc.trend(rows)["canonical_category"]) == {"Cat5", "Cat4", "Cat3", "Cat2"}
