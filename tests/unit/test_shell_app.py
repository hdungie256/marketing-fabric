from pathlib import Path
from types import SimpleNamespace

import pytest
import streamlit as st
from streamlit.testing.v1 import AppTest

import fabric_control
from app.shell import runner
from tests.unit.shell_matrix import full_registry

MAIN = str(Path(__file__).resolve().parents[2] / "app" / "main.py")
PASSWORDS = {
    "MARKETING_ANALYST_DB_PASSWORD": "pw1",
    "CRM_MARKETING_DB_PASSWORD": "pw2",
    "MARKETING_MANAGER_DB_PASSWORD": "pw3",
    "FINANCE_CONTROLLER_DB_PASSWORD": "pw4",
    "DATA_STEWARD_DB_PASSWORD": "pw5",
    "DATA_OPS_DB_PASSWORD": "pw6",
}


def overview_with_filter():
    import streamlit as st

    from app.shell import Filter, filter_bar

    values = filter_bar("campaign_overview", [Filter("campaign", "Campaign", ["All", "CMP-01", "CMP-02"])])
    st.text(f"campaign={values['campaign']}")


@pytest.fixture
def app(monkeypatch):
    for name, value in PASSWORDS.items():
        monkeypatch.setenv(name, value)
    monkeypatch.setenv("APP_DATA_MODE", "fixture")
    monkeypatch.setattr(runner, "load_pages", lambda: full_registry({"campaign_overview": overview_with_filter}))
    timings = []
    monkeypatch.setattr(fabric_control, "record_timing", lambda page, ms: timings.append(page))
    at = AppTest.from_file(MAIN, default_timeout=10)
    at.timings = timings
    return at


def login(at, code, password):
    at.run()
    at.text_input(key="_login_code").input(code)
    at.text_input(key="_login_password").input(password)
    at.button[0].click().run()
    return at


def nav_labels(at):
    return [link.proto.label for link in at.get("page_link")]


def test_invalid_login_shows_inline_error_without_role_hint(app):
    at = login(app, "UG01", "wrong")
    assert [e.value for e in at.error] == ["Invalid demo credentials"]
    assert "Marketing Analyst" not in " ".join(m.value for m in at.markdown)
    assert at.text_input(key="_login_code").value == "UG01"


def test_missing_password_env_shows_configuration_error(app, monkeypatch):
    monkeypatch.delenv("DATA_OPS_DB_PASSWORD")
    app.run()
    assert "DATA_OPS_DB_PASSWORD" in app.error[0].value
    assert not app.text_input


def test_login_lands_on_role_home(app):
    at = login(app, "ug01", "pw1")
    assert at.title[0].value == "Campaign Overview"
    assert any("Viewing as: Marketing Analyst (UG01)" in m.value for m in at.markdown)
    assert "CO5173 · Academic demo" in [c.value for c in at.sidebar.caption]
    assert "Signed in as UG01 · nav filtered to this role" in [c.value for c in at.sidebar.caption]
    assert at.timings == ["campaign_overview"]


def event_page():
    import streamlit as st

    st.text(f"event_id={st.query_params.get('event_id')}")


def test_login_opens_the_requested_page_with_its_query_params(app, monkeypatch):
    # AppTest has no browser URL, so stand in for st.context.url as a browser reports it
    context = SimpleNamespace(url="http://localhost:8501/change_history")
    monkeypatch.setattr(st, "context", context)
    monkeypatch.setattr(runner, "load_pages", lambda: full_registry({"change_history": event_page}))
    app.query_params["event_id"] = "e2"
    app.run()
    context.url = "http://localhost:8501/"  # Streamlit rewrites the URL: no page is registered before sign-in
    at = login(app, "UG01", "pw1")
    assert at.title[0].value == "Change History"
    assert "event_id=e2" in [t.value for t in at.text]
    assert at.timings == ["change_history"]  # straight there: the home page never rendered


def test_login_lands_on_home_when_the_role_cannot_open_the_requested_page(app, monkeypatch):
    monkeypatch.setattr(st, "context", SimpleNamespace(url="http://localhost:8501/pipeline_status"))
    at = login(app, "UG01", "pw1")
    assert at.title[0].value == "Campaign Overview"


def test_nav_shows_only_permitted_pages_in_group_order(app):
    at = login(app, "UG01", "pw1")
    assert nav_labels(at) == [
        "Campaign Overview",
        "Campaign Comparison",
        "Products & Categories",
        "New vs Returning",
        "Audience Builder",
        "Catalog & Glossary",
        "Lineage",
        "Change History",
    ]


def test_switch_to_role_without_current_page_redirects_home_with_toast(app):
    at = login(app, "UG01", "pw1")
    at.sidebar.selectbox(key="_role_switcher").set_value("UG05").run()
    assert at.title[0].value == "Data Quality & Exceptions"
    assert [t.value for t in at.toast] == ["Switched to Marketing Data Steward (UG05)"]
    assert "Campaign Overview" not in nav_labels(at)


def test_switch_to_role_with_current_page_stays(app):
    at = login(app, "UG01", "pw1")
    at.sidebar.selectbox(key="_role_switcher").set_value("UG03").run()
    assert at.title[0].value == "Campaign Overview"
    assert [t.value for t in at.toast] == ["Switched to Marketing Manager (UG03)"]


def test_filters_survive_role_switches(app):
    at = login(app, "UG01", "pw1")
    at.selectbox(key="_filter_campaign_overview_campaign").set_value("CMP-02").run()
    at.sidebar.selectbox(key="_role_switcher").set_value("UG05").run()
    at.sidebar.selectbox(key="_role_switcher").set_value("UG01").run()
    assert at.title[0].value == "Campaign Overview"
    assert "campaign=CMP-02" in [t.value for t in at.text]


def test_role_without_pages_sees_fallback(app, monkeypatch):
    monkeypatch.setattr(runner, "load_pages", lambda: [p for p in full_registry() if "UG06" not in p.roles])
    at = login(app, "UG06", "pw6")
    assert at.title[0].value == "No pages available"
    assert "No pages available for this role yet." in [m.value for m in at.markdown]


def test_leaving_fallback_page_lands_on_new_role_home(app, monkeypatch):
    monkeypatch.setattr(runner, "load_pages", lambda: [p for p in full_registry() if "UG05" not in p.roles])
    at = login(app, "UG01", "pw1")
    assert at.title[0].value == "Campaign Overview"
    at.sidebar.selectbox(key="_role_switcher").set_value("UG05").run()
    assert at.title[0].value == "No pages available"
    at.sidebar.selectbox(key="_role_switcher").set_value("UG03").run()
    assert at.title[0].value == "Targets"


def test_invalid_registry_stops_with_reason(app, monkeypatch):
    monkeypatch.setattr(runner, "load_pages", lambda: full_registry() + full_registry()[:1])
    at = login(app, "UG01", "pw1")
    assert "campaign_overview: duplicate key" in at.error[0].value
