from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

import fabric_control

MAIN = str(Path(__file__).resolve().parents[2] / "app" / "main.py")
TERMS = {
    "attributed_gross_value": {
        "display_name": "Attributed Gross Value",
        "notes": ["currency_unverified"],
        "synthetic": True,
    },
    "average_order_value": {
        "display_name": "Average Order Value",
        "notes": ["currency_unverified"],
        "synthetic": True,
    },
}


@pytest.fixture(autouse=True)
def stubs(monkeypatch):
    monkeypatch.setattr(fabric_control, "term", lambda term_id: TERMS.get(term_id))
    calls = []
    monkeypatch.setattr(fabric_control, "record_timing", lambda page, ms: calls.append(page))
    return calls


def _wrapped_metrics_script():
    from datetime import UTC, datetime

    import streamlit as st

    from app.shell import PageSpec, metric, session
    from app.shell.page import wrap

    def render():
        freshness = datetime(2026, 10, 5, 7, 5, tzinfo=UTC)
        left, right = st.columns(2)
        with left:
            metric("attributed_gross_value", 123456.7, freshness, kind="money")
        with right:
            metric("average_order_value", 95.5, freshness, kind="money")

    session.set_role("UG01")
    wrap(PageSpec("campaign_overview", "Campaign Overview", "Campaigns", render, frozenset({"UG01"})))()


def test_metric_inside_wrapper_puts_currency_note_once_in_footnote_strip(stubs):
    at = AppTest.from_function(_wrapped_metrics_script).run()
    assert not at.exception
    captions = [c.value for c in at.caption]
    assert captions.count("Currency of monetary values is not stated in the source (R10).") == 1
    assert "123,457" in [m.value for m in at.markdown]
    assert stubs == ["campaign_overview"]


def test_real_app_logs_in_to_campaign_overview(monkeypatch):
    for name, value in {
        "MARKETING_ANALYST_DB_PASSWORD": "pw1",
        "CRM_MARKETING_DB_PASSWORD": "pw2",
        "MARKETING_MANAGER_DB_PASSWORD": "pw3",
        "FINANCE_CONTROLLER_DB_PASSWORD": "pw4",
        "DATA_STEWARD_DB_PASSWORD": "pw5",
        "DATA_OPS_DB_PASSWORD": "pw6",
    }.items():
        monkeypatch.setenv(name, value)
    monkeypatch.setenv("APP_DATA_MODE", "fixture")
    at = AppTest.from_file(MAIN, default_timeout=10).run()
    at.text_input(key="_login_code").input("UG01")
    at.text_input(key="_login_password").input("pw1")
    at.button[0].click().run()
    assert not at.exception
    assert at.title[0].value == "Campaign Overview"
    assert not any(c.value.startswith("Placeholder") for c in at.caption)
