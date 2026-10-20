from datetime import UTC, datetime, timedelta

import pandas as pd
import pytest
from streamlit.testing.v1 import AppTest

import fabric_control
from app.pages.changes import change_history as page
from app.shell import NotPermittedError, fmt_time
from fabric_control.glossary import load_terms
from tests.unit.test_change_history import EVENT, T0, log, runs

OLD = T0 - timedelta(hours=1)
E2 = {
    **EVENT,
    "event_id": "e2",
    "emitted_at": datetime(2026, 10, 19, 20, 0, tzinfo=UTC),  # 03:00 on 2026-10-20 in APP_TZ (UTC+7)
    "keys": '{"campaign_id": "CMP19_01", "date": "2019-11-01"}',
}


def events():
    return pd.DataFrame([{**EVENT, "keys": '{"campaign_id": "CMP19_05", "date": "2019-11-12"}'}, E2])


class Source:
    """campaign_spend_allocated keeps 2 rows from before the edit; contribution is denied."""

    def read(self, dataset_id):
        if dataset_id == "mart_finance.contribution":
            raise NotPermittedError(dataset_id)
        if dataset_id == "mart_shared.campaign_spend_allocated":
            return pd.DataFrame({"allocated": [1.0, 2.0, 3.0], "_refreshed_at": [OLD, OLD, T0 + timedelta(seconds=30)]})
        return pd.DataFrame()


def _script(role="UG01"):
    from app.pages.changes.change_history import render
    from app.shell import session

    session.set_role(role)
    render()


@pytest.fixture(autouse=True)
def _env(monkeypatch):
    monkeypatch.setenv("APP_DATA_MODE", "pg")
    monkeypatch.setenv("APP_TZ", "Asia/Ho_Chi_Minh")
    terms = load_terms()
    monkeypatch.setattr(fabric_control, "term", lambda t: terms.get(t))
    monkeypatch.setattr(fabric_control, "effective_matrix", lambda: [])
    monkeypatch.setattr(page, "current_source", lambda: Source())


def _app(monkeypatch, loaded=None, event_id=None, role="UG01"):
    if loaded is None:
        loaded = (events(), runs(), log())
    monkeypatch.setattr(page, "load", lambda role: loaded)
    at = AppTest.from_function(_script, kwargs={"role": role})
    if event_id:
        at.query_params["event_id"] = event_id
    at.run()
    assert not at.exception, at.exception
    text = " ".join(e.value for e in [*at.subheader, *at.markdown, *at.caption])
    return at, text


def test_empty_state_without_events(monkeypatch):
    _, text = _app(monkeypatch, (events()[0:0], runs()[0:0], log()[0:0]))
    assert "No source changes recorded yet." in text


def test_fixture_mode_shows_empty_state(monkeypatch):
    monkeypatch.setenv("APP_DATA_MODE", "fixture")
    monkeypatch.setattr(page, "load", lambda role: pytest.fail("fixture mode must not read ops views"))
    at = AppTest.from_function(_script).run()
    assert not at.exception, at.exception
    assert "No source changes recorded yet." in " ".join(m.value for m in at.markdown)


def test_summary_line_text(monkeypatch):
    _, text = _app(monkeypatch)
    assert f"4 metrics changed** · 2 unchanged kept refresh time {fmt_time(OLD)}" in text
    assert "How the change flowed" in text and "Not downstream of spend, not refreshed:" in text
    assert "and" in text.split("Not downstream of spend, not refreshed:")[1]


def test_event_id_query_param_selects_event(monkeypatch):
    at, text = _app(monkeypatch, event_id="e2")
    assert at.selectbox(key="change_event").value == "e2"
    assert "No values changed for this event." in text


def test_info_button_only_for_glossary_metrics(monkeypatch):
    at, text = _app(monkeypatch)
    assert len([b for b in at.button if b.label == "ⓘ"]) == 2
    assert "\u2212200.00" in text and "+200.00" in text  # signed with the U+2212 minus, 2 decimals
    assert "1,356.33" in text and "1,156.33" in text
    assert "CMP19_05. Select ⓘ for the metric definition." in text


def test_shown_on_links_to_page(monkeypatch):
    at, _ = _app(monkeypatch, role="UG03")
    labels = [b.label for b in at.button if b.key and b.key.startswith("change-page-")]
    assert labels == ["Budget & Spend", "Budget & Spend", "Targets", "Contribution"]
    at.button(key="change-page-2").click().run()
    assert at.session_state["_shell_redirect"] == "targets"


def test_shown_on_is_text_for_pages_the_role_cannot_open(monkeypatch):
    at, text = _app(monkeypatch, role="UG04")
    labels = [b.label for b in at.button if b.key and b.key.startswith("change-page-")]
    assert labels == ["Budget & Spend", "Budget & Spend", "Contribution"]  # UG04 has no Targets page
    assert "Targets" in text


def test_saved_at_shows_date_and_time_in_app_tz(monkeypatch):
    at, _ = _app(monkeypatch)
    assert list(at.dataframe[0].value["Saved at"]) == ["2026-10-20 17:42", "2026-10-20 03:00"]


def test_no_downstream_caption_when_everything_refreshed(monkeypatch):
    monkeypatch.setattr(page.ch, "not_downstream", lambda event: [])
    _, text = _app(monkeypatch)
    assert "Not downstream of spend" not in text


def test_ug01_without_contribution_access_still_renders(monkeypatch):
    _, text = _app(monkeypatch)
    assert "Changed values" in text
