from datetime import UTC, date, datetime

import pandas as pd
import pytest
from streamlit.testing.v1 import AppTest

import fabric_control
from app.pages.campaign import overview

AT = datetime(2026, 10, 12, 7, 5, tzinfo=UTC)
TERMS = {
    "attributed_orders": ("Attributed Orders", ["attributed_not_incremental"]),
    "attributed_buyers": ("Attributed Buyers", ["attributed_not_incremental"]),
    "attributed_gross_value": ("Attributed Gross Value", ["currency_unverified", "attributed_not_incremental"]),
    "average_order_value": ("Average Order Value", ["currency_unverified"]),
}


def frame():
    rows = []
    for pid, label, start, end in [
        ("FY2019", "Jan–Dec 2019", date(2019, 1, 1), date(2019, 12, 31)),
        ("2019-Q2", "Q2 2019", date(2019, 4, 1), date(2019, 6, 30)),
    ]:
        for cid, name, orders in [
            ("ALL", "All campaigns", 1290),
            ("CMP19_01", "New-year Apparel", 278),
            ("CMP19_02", "Spring Nest", 442),
        ]:
            n = 0 if (pid, cid) == ("2019-Q2", "CMP19_01") else orders
            rows.append(
                {
                    "period_id": pid,
                    "period_label": label,
                    "period_start": start,
                    "period_end": end,
                    "campaign_id": cid,
                    "campaign_name": name,
                    "attributed_orders": n,
                    "attributed_buyers": n // 3,
                    "attributed_gross_value": n * 217.14,
                    "average_order_value": 217.14 if n else None,
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
    monkeypatch.setattr(overview, "current_source", lambda: Source())


def _script():
    from app.pages.campaign import overview
    from app.shell import PageSpec, session
    from app.shell.page import wrap

    session.set_role("UG01")
    wrap(PageSpec("campaign_overview", "Campaign Overview", "Campaigns", overview.render, frozenset({"UG01"})))()


def markdown(at):
    return [m.value for m in at.markdown]


def test_whole_period_shows_four_cards_and_campaign_table():
    at = AppTest.from_function(_script).run()
    assert not at.exception
    text = " ".join(markdown(at))
    for label, _ in TERMS.values():
        assert label in text
    assert "1,290" in markdown(at)
    assert "Viewing as: Marketing Analyst (UG01)" in text
    assert len(at.dataframe[0].value) == 2


def test_campaign_without_orders_shows_empty_state():
    at = AppTest.from_function(_script).run()
    at.selectbox(key="_filter_campaign_overview_period").set_value("2019-Q2").run()
    at.selectbox(key="_filter_campaign_overview_campaign").set_value("CMP19_01").run()
    assert not at.exception
    text = " ".join(markdown(at))
    assert "No attributed orders for CMP19_01 in this period." in text
    assert "Clear the Campaign filter to see all." in [c.value for c in at.caption]
    assert "1,290" not in markdown(at)
    assert not at.dataframe


def test_stale_saved_filter_falls_back_to_first_option():
    def script():
        from app.pages.campaign import overview
        from app.shell import PageSpec, session
        from app.shell.page import wrap

        session.set_role("UG01")
        session.filters("campaign_overview")["campaign"] = "CMP-01"
        wrap(PageSpec("campaign_overview", "Campaign Overview", "Campaigns", overview.render, frozenset({"UG01"})))()

    at = AppTest.from_function(script).run()
    assert not at.exception
    assert at.selectbox(key="_filter_campaign_overview_campaign").value == "ALL"


def test_unknown_term_shows_error_banner(monkeypatch):
    monkeypatch.setattr(fabric_control, "term", lambda t: None)
    at = AppTest.from_function(_script).run()
    assert "Could not load this page" in " ".join(e.value for e in at.error)
