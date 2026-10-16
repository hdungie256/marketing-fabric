from datetime import UTC, date, datetime

import pandas as pd
import pytest
from streamlit.testing.v1 import AppTest

import fabric_control
from app.pages.campaign import new_returning
from app.shell import NOTE_TEXT

AT = datetime(2026, 10, 16, 7, 5, tzinfo=UTC)
R9 = ["first_in_observed_history"]
TERMS = {
    "first_observed_buyers": ("First Observed Buyers", R9),
    "returning_buyers": ("Returning Buyers", R9),
    "attributed_buyers": ("Attributed Buyers", ["attributed_not_incremental"]),
}


def frame():
    rows = []
    for pid, label, start, end in [
        ("FY2019", "Jan–Dec 2019", date(2019, 1, 1), date(2019, 12, 31)),
        ("2019-Q2", "Q2 2019", date(2019, 4, 1), date(2019, 6, 30)),
    ]:
        for cid, name, total, first in [
            ("ALL", "All campaigns", 456, 300),
            ("CMP19_01", "New-year Apparel", 100, 60),
            ("CMP19_02", "Spring Nest", 200, 150),
        ]:
            if (pid, cid) == ("2019-Q2", "CMP19_01"):
                total = first = 0
            rows.append(
                {
                    "period_id": pid,
                    "period_label": label,
                    "period_start": start,
                    "period_end": end,
                    "campaign_id": cid,
                    "campaign_name": name,
                    "attributed_buyers": total,
                    "first_observed_buyers": first,
                    "returning_buyers": total - first,
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
    monkeypatch.setattr(new_returning, "current_source", lambda: Source())


def _script():
    from app.pages.campaign import new_returning
    from app.shell import PageSpec, session
    from app.shell.page import wrap

    session.set_role("UG02")
    wrap(PageSpec("new_vs_returning", "New vs Returning", "Campaigns", new_returning.render, frozenset({"UG02"})))()


def test_three_cards_with_r9_note():
    at = AppTest.from_function(_script).run()
    assert not at.exception
    text = " ".join(m.value for m in at.markdown)
    for label in ("First Observed Buyers", "Returning Buyers", "Attributed Buyers"):
        assert label in text
    assert NOTE_TEXT["first_in_observed_history"] in [c.value for c in at.caption]
    at.toggle(key="new_returning_chart_table_view")


def test_campaign_without_buyers_shows_empty_state():
    at = AppTest.from_function(_script).run()
    at.selectbox(key="_filter_new_vs_returning_period").set_value("2019-Q2").run()
    at.selectbox(key="_filter_new_vs_returning_campaign").set_value("CMP19_01").run()
    assert not at.exception
    assert "No attributed buyers for CMP19_01 in this period." in " ".join(m.value for m in at.markdown)
    assert "Clear the Campaign filter to see all." in [c.value for c in at.caption]
    assert not at.dataframe
