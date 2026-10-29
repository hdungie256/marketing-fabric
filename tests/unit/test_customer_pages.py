"""Stories 5.1/5.2 AppTest: RFM distribution, win-back filter, empty states, prefill."""

import pandas as pd
import pytest
from streamlit.testing.v1 import AppTest

from app.pages.customer import rfm_segments, win_back
from app.services import customers as svc


def frame():
    return pd.DataFrame(
        [
            (1, 5, 5, 6, 5, 600.0, 5, "Champions", "Apparel"),
            (2, 40, 3, 2, 2, 100.0, 2, "Needs Attention", "Apparel,Nest"),
            (3, 300, 1, 1, 1, 10.0, 1, "Lost", "Nest"),
            (4, 200, 1, 4, 5, 500.0, 5, "Can't Lose", "Fun"),
        ],
        columns=[
            "customer_id",
            "recency_days",
            "recency_score",
            "frequency_orders",
            "frequency_score",
            "monetary_value",
            "monetary_score",
            "segment",
            "categories",
        ],
    )


class Source:
    def read(self, dataset_id):
        assert dataset_id == svc.DATASET
        return frame()


@pytest.fixture(autouse=True)
def stubs(monkeypatch):
    monkeypatch.setattr(rfm_segments, "current_source", lambda: Source())
    monkeypatch.setattr(win_back, "current_source", lambda: Source())


def _rfm_script():
    from app.pages.customer import rfm_segments

    rfm_segments.render()


def _winback_script():
    from app.pages.customer import win_back

    win_back.render()


def test_rfm_page_shows_distribution_and_segment_list():
    at = AppTest.from_function(_rfm_script).run()
    assert not at.exception
    assert "Buyers by RFM segment" in " ".join(m.value for m in at.markdown)
    assert set(at.selectbox(key="_filter_rfm_segments_segment").options) == {
        "Champions",
        "Can't Lose",
        "Needs Attention",
        "Lost",
    }


def test_rfm_page_totals_reconcile_with_buyers():
    summary = svc.segment_summary(frame())
    assert summary["customers"].sum() == svc.buyer_count(frame()) == 4


def test_win_back_lists_only_lapsed_high_value():
    at = AppTest.from_function(_winback_script).run()
    assert not at.exception
    assert at.dataframe[0].value["customer_id"].tolist() == [4]


def test_win_back_states_count_rule_and_as_of_date():
    at = AppTest.from_function(_winback_script).run()
    assert not at.exception
    assert "**1 of 4 buyers** · (F = 5 or M = 5) and R = 1 (R18) · as of 2019-12-31" in [m.value for m in at.markdown]


def test_win_back_empty_filter_shows_exact_message():
    at = AppTest.from_function(_winback_script).run()
    at.selectbox(key="_filter_win_back_category").set_value("Apparel").run()
    assert not at.exception
    assert "No lapsed high-value customers for this filter." in " ".join(m.value for m in at.markdown)


def test_win_back_button_opens_audience_builder_prefilled():
    at = AppTest.from_function(_winback_script).run()
    at.selectbox(key="_filter_win_back_category").set_value("Fun").run()
    at.button(key="win_back-to-builder").click().run()
    assert not at.exception
    assert at.session_state["audience_prefill"] == {
        "segment": "All",
        "category": "Fun",
        "min_orders": 0,
        "win_back": True,
    }
    assert at.session_state["_shell_redirect"] == "audience_builder"
    assert at.session_state["_shell_toast"] == "Audience Builder prefilled with the Win-back criteria"
