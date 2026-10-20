import json
import urllib.request
from datetime import UTC, date, datetime
from decimal import Decimal

import pandas as pd
from streamlit.testing.v1 import AppTest

import fabric_control
from app.services import spend_edit
from app.services.spend_edit import SpendServiceUnavailable, field_errors, put_spend

EVENT = {
    "event_id": "e1",
    "emitted_at": "2026-10-20T07:00:00+00:00",
    "source": "raw/spend/campaign_spend",
    "keys": {"campaign_id": "CMP19_05", "date": "2019-11-12"},
}


def test_put_spend_sends_role_header_and_body(monkeypatch):
    seen = {}

    class Response:
        status = 200

        def read(self):
            return b'{"event": {}, "dag_run_id": "r1"}'

        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

    def fake(request, timeout):
        seen["request"] = request
        return Response()

    monkeypatch.setenv("API_URL", "http://api:8000")
    monkeypatch.setattr(urllib.request, "urlopen", fake)
    status, body = put_spend("CMP19_05", date(2019, 11, 12), Decimal("1156.33"), "UG04")
    request = seen["request"]
    assert (status, body["dag_run_id"]) == (200, "r1")
    assert request.get_method() == "PUT"
    assert request.full_url.endswith("/spend/campaign_spend/CMP19_05/2019-11-12")
    assert json.loads(request.data) == {"allocated_online_spend": "1156.33"}
    assert request.get_header("X-fabric-role") == "UG04"


def test_field_errors_reads_detail():
    detail = {"field": "allocated_online_spend", "reason": "3500 is above that day's online spend 3390.82"}
    assert field_errors(422, {"detail": detail}) == {detail["field"]: detail["reason"]}
    assert field_errors(403, {"detail": {"reason": "no"}}) == {}


def _form(missing=False):
    from datetime import date
    from decimal import Decimal

    import pandas as pd

    from app.shell.components.spend_edit import spend_edit_form

    days = pd.DataFrame(
        {
            "campaign_id": ["CMP19_05", "CMP19_05", "CMP19_01"],
            "campaign_name": ["Holiday Nest", "Holiday Nest", "Spring"],
            "date": [date(2019, 11, 12), date(2019, 11, 13), date(2019, 1, 15)],
        }
    )
    recon = pd.DataFrame(
        {
            "date": [date(2019, 11, 12), date(2019, 11, 13), date(2019, 1, 15)],
            "online_spend": [None if missing else Decimal("3390.82"), Decimal("2400.95"), Decimal("100")],
            "allocated": [Decimal("1356.33"), Decimal("936.37"), Decimal("10")],
            "unallocated": [Decimal("2034.49"), Decimal("1464.58"), Decimal("90")],
        }
    )
    spend_edit_form(days, recon)


def _run(monkeypatch, answer=None, value=1156.33):
    calls = []

    def fake(*args, **kwargs):
        calls.append(args)
        if isinstance(answer, Exception):
            raise answer
        return answer

    monkeypatch.setenv("APP_DATA_MODE", "pg")
    monkeypatch.setattr(spend_edit, "put_spend", fake)
    at = AppTest.from_function(_form)
    at.session_state["_shell_role"] = "UG04"
    at.run()
    at.selectbox[0].select("CMP19_05").run()
    if value is not None:
        at.number_input[0].set_value(value)
    at.button[0].click().run()
    assert not at.exception, at.exception
    return at, calls


def _errors(at):
    return " ".join(e.value for e in at.error)


def test_form_shows_hint_for_chosen_day(monkeypatch):
    monkeypatch.setenv("APP_DATA_MODE", "pg")
    at = AppTest.from_function(_form).run()
    at.selectbox[0].select("CMP19_05").run()
    text = " ".join(c.value for c in at.caption)
    assert "Online spend that day is 3,390.82. Allocated must be between 0 and that amount." in text
    assert at.button[0].label == "Save change"


def test_hint_shows_dash_when_online_spend_missing(monkeypatch):
    monkeypatch.setenv("APP_DATA_MODE", "pg")
    at = AppTest.from_function(_form, kwargs={"missing": True}).run()
    at.selectbox[0].select("CMP19_05").run()
    assert not at.exception, at.exception
    assert "Online spend that day is —." in " ".join(c.value for c in at.caption)


def test_put_spend_wraps_error_body_read_failure(monkeypatch):
    import io
    import urllib.error

    import pytest

    class Broken(io.BytesIO):
        def read(self, *args):
            raise ConnectionResetError("reset")

    def fake(request, timeout):
        raise urllib.error.HTTPError(request.full_url, 500, "Server Error", {}, Broken())

    monkeypatch.setenv("API_URL", "http://api:8000")
    monkeypatch.setattr(urllib.request, "urlopen", fake)
    with pytest.raises(SpendServiceUnavailable):
        put_spend("CMP19_05", date(2019, 11, 12), Decimal("1"), "UG04")


def test_empty_value_does_not_call_api(monkeypatch):
    at, calls = _run(monkeypatch, value=None)
    assert calls == []
    assert "Enter a value" in _errors(at)


def test_422_shows_reason_under_field_and_keeps_values(monkeypatch):
    reason = "3500 is above that day's online spend 3390.82"
    at, calls = _run(monkeypatch, (422, {"detail": {"field": "allocated_online_spend", "reason": reason}}))
    assert len(calls) == 1
    assert reason in _errors(at)
    assert at.selectbox[0].value == "CMP19_05"
    assert spend_edit.EVENT_KEY not in at.session_state


def test_200_stores_event_and_toasts(monkeypatch):
    at, calls = _run(monkeypatch, (200, {"event": EVENT, "dag_run_id": "r1"}))
    assert calls[0][:4] == ("CMP19_05", date(2019, 11, 12), Decimal("1156.33"), "UG04")
    stored = at.session_state[spend_edit.EVENT_KEY]
    assert stored["event"] == EVENT and stored["campaign_name"] == "Holiday Nest"
    assert stored["old"] == {"allocated": Decimal("1356.33"), "unallocated": Decimal("2034.49")}
    assert stored["new"] == Decimal("1156.33")
    assert [t.value for t in at.toast] == ["Change saved · partial refresh started"]
    assert at.number_input[0].value is None  # the rerun after save clears the value at once
    at.run()
    assert not at.toast  # shown once


def test_403_shows_reason_banner(monkeypatch):
    at, _ = _run(monkeypatch, (403, {"detail": {"reason": "UG03 may not edit spend"}}))
    assert "UG03 may not edit spend" in _errors(at)


def test_502_shows_saved_but_not_started(monkeypatch):
    at, _ = _run(monkeypatch, (502, {"detail": {"reason": "airflow down", "event": EVENT}}))
    assert "Change saved, but the refresh did not start: airflow down" in _errors(at)
    assert spend_edit.EVENT_KEY not in at.session_state


def test_502_does_not_repeat_the_api_prefix(monkeypatch):
    reason = "Change saved but partial refresh did not start: airflow down"  # api/services/spend.py wording
    at, _ = _run(monkeypatch, (502, {"detail": {"reason": reason, "event": EVENT}}))
    assert "Change saved, but the refresh did not start: airflow down" in _errors(at)
    assert "partial refresh" not in _errors(at)


def test_put_spend_wraps_dropped_connection_and_bad_json(monkeypatch):
    import http.client

    import pytest

    class Garbage:
        status = 200

        def read(self):
            return b"<html>proxy error</html>"

        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

    monkeypatch.setenv("API_URL", "http://api:8000")
    for answer in (http.client.RemoteDisconnected("closed"), ConnectionResetError("reset"), Garbage()):

        def fake(request, timeout, answer=answer):
            if isinstance(answer, Exception):
                raise answer
            return answer

        monkeypatch.setattr(urllib.request, "urlopen", fake)
        with pytest.raises(SpendServiceUnavailable):
            put_spend("CMP19_05", date(2019, 11, 12), Decimal("1"), "UG04")


def test_unreachable_api_shows_banner(monkeypatch):
    at, _ = _run(monkeypatch, SpendServiceUnavailable("connection refused"))
    assert "The spend service did not answer" in _errors(at)
    assert "connection refused" in _errors(at)


def test_fixture_mode_disables_save(monkeypatch):
    monkeypatch.setenv("APP_DATA_MODE", "fixture")
    at = AppTest.from_function(_form).run()
    assert at.button[0].disabled
    assert "Saving needs the live stack (APP_DATA_MODE=pg)." in " ".join(c.value for c in at.caption)


STEPS = [
    "unified/campaign_spend",
    "unified/daily_spend",
    "mart_shared.campaign_spend_allocated",
    "mart_shared.spend_reconciliation",
    "mart_campaign.target_achievement",
    "mart_finance.budget_daily",
    "mart_finance.contribution",
    "mart_finance.contribution_sku",
]


def _strip():
    from app.shell.components.spend_edit import progress_strip

    progress_strip()


def _strip_app(monkeypatch, runs):
    from app.shell.components import spend_edit as component

    affected = [{"dataset_id": "raw/spend/campaign_spend", "job_id": "raw"}]
    affected += [{"dataset_id": d, "job_id": f"job_{i}"} for i, d in enumerate(STEPS)]
    monkeypatch.setattr(fabric_control, "affected_by", lambda event: affected)
    monkeypatch.setattr(component, "_read", lambda role: (runs, pd.DataFrame()))
    at = AppTest.from_function(_strip)
    at.session_state["_shell_role"] = "UG04"
    event = {**EVENT, "emitted_at": datetime.now(UTC).isoformat()}  # fresh, so not timed out
    state = {"event": event, "dag_run_id": "r1", "campaign_name": "Holiday Nest", "old": {}, "new": Decimal("1")}
    at.session_state[spend_edit.EVENT_KEY] = state
    at.run()
    assert not at.exception, at.exception
    return at, " ".join(m.value for m in at.markdown) + " " + " ".join(c.value for c in at.caption)


def test_strip_lists_eight_steps_and_header(monkeypatch):
    runs = pd.DataFrame({"event_id": ["e1"], "job_id": ["job_0"], "status": ["running"]})
    at, text = _strip_app(monkeypatch, runs)
    assert "Refreshing 8 datasets for Holiday Nest, 2019-11-12" in text
    assert "Affects Budget & Spend, Contribution and Targets" in text
    for dataset_id in STEPS:
        assert f"`{dataset_id}`" in text
    assert "Spend source data" in text and "running" in text and "queued" in text
    assert "Full run detail is on Pipeline Status (Data Ops role)." in text
    assert not at.button


def test_strip_is_noop_without_event():
    at = AppTest.from_function(_strip).run()
    assert not at.exception and not at.markdown


def test_strip_done_links_to_change_history(monkeypatch):
    runs = pd.DataFrame({"event_id": ["e1"] * 8, "job_id": [f"job_{i}" for i in range(8)], "status": ["success"] * 8})
    at, text = _strip_app(monkeypatch, runs)
    assert "0 metrics changed" in text
    at.button[0].click().run()
    assert at.session_state["_shell_redirect"] == "change_history"
    assert at.session_state["_shell_redirect_params"] == {"event_id": "e1"}


def test_strip_failed_run_shows_cause(monkeypatch):
    runs = pd.DataFrame({"event_id": ["e1"], "job_id": ["job_0"], "status": ["failed"], "failing_step": ["dq_gate"]})
    at, text = _strip_app(monkeypatch, runs)
    assert "Refresh stopped: dq_gate. See Pipeline Status." in text
    assert "skipped" in text and not at.button


def test_budget_spend_save_shows_refreshing_at_once(monkeypatch):
    """Regression: the save run must rerun the page so cards and the edited row see the event in flight."""
    import streamlit as st

    from app.pages.finance import budget_spend
    from fabric_control.glossary import load_terms
    from tests.unit.test_budget_spend_page import Source, _role_script

    monkeypatch.setenv("APP_DATA_MODE", "pg")
    monkeypatch.setenv("APP_TZ", "UTC")
    terms = load_terms()
    monkeypatch.setattr(fabric_control, "term", lambda t: terms.get(t))
    monkeypatch.setattr(fabric_control, "effective_matrix", lambda: [])
    monkeypatch.setattr(budget_spend, "current_source", lambda: Source())
    flying = frozenset({"mart_finance.budget_daily", "mart_shared.campaign_spend_allocated", budget_spend.RECON})
    monkeypatch.setattr(
        budget_spend, "current_in_flight", lambda c: flying if spend_edit.EVENT_KEY in st.session_state else frozenset()
    )
    monkeypatch.setattr(budget_spend, "watch", lambda c, s: None)
    monkeypatch.setattr(budget_spend, "progress_strip", lambda: None)
    event = {
        **EVENT,
        "emitted_at": "2099-01-01T00:00:00+00:00",
        "keys": {"campaign_id": "CMP19_01", "date": "2019-01-16"},
    }
    monkeypatch.setattr(spend_edit, "put_spend", lambda *a, **k: (200, {"event": event, "dag_run_id": "r1"}))
    at = AppTest.from_function(_role_script, kwargs={"role": "UG04"}).run()
    day = at.selectbox(key="spend_edit_date_CMP19_01")
    day.set_value(day.options[1]).run()
    at.number_input[0].set_value(5.0).run()
    next(b for b in at.button if b.label == "Save change").click().run()
    assert not at.exception, at.exception
    assert "Refreshing" in " ".join(m.value for m in at.markdown)
    [notes] = [d.value["note"] for d in at.dataframe if "note" in d.value.columns]
    assert any("updating" in n for n in notes)
    assert not any("Refresh stopped" in n for n in notes)
    assert [t.value for t in at.toast] == ["Change saved · partial refresh started"]


def test_see_change_history_opens_that_event(monkeypatch):
    """Strip done -> redirect with ?event_id -> Change History selects that event (runner keeps the param)."""
    from pathlib import Path

    from app.pages.changes import change_history
    from app.shell import runner
    from app.shell.components import spend_edit as component
    from tests.unit import test_change_history_page as ch_page
    from tests.unit.shell_matrix import full_registry
    from tests.unit.test_shell_app import PASSWORDS, login

    for name, value in PASSWORDS.items():
        monkeypatch.setenv(name, value)
    monkeypatch.setenv("APP_DATA_MODE", "pg")
    from fabric_control.glossary import load_terms

    terms = load_terms()
    monkeypatch.setattr(fabric_control, "term", lambda t: terms.get(t))
    monkeypatch.setattr(fabric_control, "effective_matrix", lambda: [])
    monkeypatch.setattr(fabric_control, "record_timing", lambda page, ms: None)
    monkeypatch.setattr(change_history, "current_source", lambda: ch_page.Source())
    monkeypatch.setattr(change_history, "load", lambda role: (ch_page.events(), ch_page.runs(), ch_page.log()))
    affected = [{"dataset_id": "raw/spend/campaign_spend", "job_id": "raw"}]
    affected += [{"dataset_id": d, "job_id": f"job_{i}"} for i, d in enumerate(STEPS)]
    monkeypatch.setattr(fabric_control, "affected_by", lambda event: affected)
    done = pd.DataFrame({"event_id": ["e2"] * 8, "job_id": [f"job_{i}" for i in range(8)], "status": ["success"] * 8})
    monkeypatch.setattr(component, "_read", lambda role: (done, pd.DataFrame()))
    renders = {"budget_spend": component.progress_strip, "change_history": change_history.render}
    monkeypatch.setattr(runner, "load_pages", lambda: full_registry(renders))
    main = str(Path(__file__).resolve().parents[2] / "app" / "main.py")
    at = AppTest.from_file(main, default_timeout=10)
    event = {**EVENT, "event_id": "e2", "emitted_at": datetime.now(UTC).isoformat()}
    at.session_state[spend_edit.EVENT_KEY] = {"event": event, "campaign_name": "Spring", "old": {}, "new": Decimal("1")}
    login(at, "UG04", "pw4")
    assert not at.exception, at.exception
    next(b for b in at.button if b.label == "See Change History").click().run()
    assert not at.exception, at.exception
    assert at.selectbox(key="change_event").value == "e2"  # not the default (most recent) e1
