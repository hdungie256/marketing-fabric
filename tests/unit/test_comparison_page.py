from datetime import UTC, date, datetime

import pandas as pd
import pytest
from streamlit.testing.v1 import AppTest

import fabric_control
from app.pages.campaign import comparison

AT = datetime(2026, 10, 16, 7, 5, tzinfo=UTC)
TERMS = {
    "attributed_orders": ("Attributed Orders", ["attributed_not_incremental"]),
    "attributed_buyers": ("Attributed Buyers", ["attributed_not_incremental"]),
    "attributed_gross_value": ("Attributed Gross Value", ["currency_unverified", "attributed_not_incremental"]),
    "average_order_value": ("Average Order Value", ["currency_unverified"]),
}
CAMPAIGNS = [
    ("CMP19_01", "New-year Apparel", "Paid Search"),
    ("CMP19_02", "Spring Nest", "Paid Social"),
    ("CMP19_03", "Summer Drinkware", "Email CRM"),
    ("CMP19_04", "Autumn Search", "Paid Search"),
    ("CMP19_05", "Holiday Email", "Email CRM"),
]


def frame():
    groups = [("campaign", cid, name, channel) for cid, name, channel in CAMPAIGNS]
    groups += [("channel", c, c, c) for c in ("Paid Search", "Paid Social", "Email CRM")]
    rows = []
    for pid, label, start, end in [
        ("FY2019", "Jan–Dec 2019", date(2019, 1, 1), date(2019, 12, 31)),
        ("2019-Q1", "Q1 2019", date(2019, 1, 1), date(2019, 3, 31)),
    ]:
        for i, (kind, gid, name, channel) in enumerate(groups):
            n = 100 + i
            rows.append(
                {
                    "period_id": pid,
                    "period_label": label,
                    "period_start": start,
                    "period_end": end,
                    "compare_by": kind,
                    "group_id": gid,
                    "group_name": name,
                    "channel": channel,
                    "attributed_orders": n,
                    "attributed_buyers": n // 2,
                    "attributed_gross_value": n * 217.14,
                    "average_order_value": 217.14,
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
    monkeypatch.setattr(comparison, "current_source", lambda: Source())


def _script():
    from app.pages.campaign import comparison
    from app.shell import PageSpec, session
    from app.shell.page import wrap

    session.set_role("UG03")
    wrap(PageSpec("campaign_comparison", "Campaign Comparison", "Campaigns", comparison.render, frozenset({"UG03"})))()


def test_default_is_fy2019_by_campaign():
    at = AppTest.from_function(_script).run()
    assert not at.exception
    assert at.selectbox(key="_filter_campaign_comparison_period").value == "FY2019"
    table = at.dataframe[0].value
    assert len(table) == 5
    for label, _ in TERMS.values():
        assert label in table.columns
    assert len([b for b in at.button if b.label.startswith("ⓘ")]) == 4


def test_compare_by_channel_shows_three_channels():
    at = AppTest.from_function(_script).run()
    at.selectbox(key="_filter_campaign_comparison_compare_by").set_value("channel").run()
    assert not at.exception
    table = at.dataframe[0].value
    assert sorted(table["Channel"]) == ["Email CRM", "Paid Search", "Paid Social"]


def test_stale_saved_filter_falls_back_to_first_option():
    def script():
        from app.pages.campaign import comparison
        from app.shell import PageSpec, session
        from app.shell.page import wrap

        session.set_role("UG03")
        session.filters("campaign_comparison")["compare_by"] = "region"
        wrap(
            PageSpec("campaign_comparison", "Campaign Comparison", "Campaigns", comparison.render, frozenset({"UG03"}))
        )()

    at = AppTest.from_function(script).run()
    assert not at.exception
    assert at.selectbox(key="_filter_campaign_comparison_compare_by").value == "campaign"


def test_table_leads_with_the_charted_metric_and_notes_r6_r7():
    from app.pages.campaign import comparison

    at = AppTest.from_function(_script).run()
    at.selectbox(key="_filter_campaign_comparison_metric").set_value("attributed_orders").run()
    assert not at.exception
    columns = list(at.dataframe[0].value.columns)
    assert columns.index(TERMS["attributed_orders"][0]) < columns.index(TERMS["attributed_gross_value"][0])
    footnotes = [t.value for t in at.caption]
    assert all(note in footnotes for note in comparison.NOTES)
