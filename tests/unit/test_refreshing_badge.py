from streamlit.testing.v1 import AppTest

import fabric_control
from fabric_control.glossary import load_terms


def _app(monkeypatch, in_flight, stale=False):
    terms = load_terms()
    monkeypatch.setattr(fabric_control, "term", lambda t: terms.get(t))
    monkeypatch.setattr(fabric_control, "status", lambda d: {"stale": stale, "datasets": [d]})
    at = AppTest.from_function(_body, kwargs={"flag": in_flight}).run()
    assert not at.exception, at.exception
    return " ".join(m.value for m in at.markdown)


def _body(flag):
    from datetime import UTC, datetime

    from app.shell import metric

    ids = frozenset({"mart_shared.campaign_spend_allocated"}) if flag else frozenset()
    metric("allocated_spend", 1, datetime(2026, 10, 13, 7, 0, tzinfo=UTC), kind="money", in_flight=ids)


def test_metric_shows_refreshing_when_dataset_in_flight(monkeypatch):
    text = _app(monkeypatch, True)
    assert "Refreshing…" in text and "Refreshed" not in text


def test_metric_keeps_fresh_badge_otherwise(monkeypatch):
    text = _app(monkeypatch, False)
    assert "Refreshed" in text and "Refreshing" not in text


def test_stale_wins_over_refreshing(monkeypatch):
    text = _app(monkeypatch, True, stale=True)
    assert "Using previous version" in text and "Refreshing" not in text


def test_current_in_flight_is_empty_in_fixture_mode(monkeypatch):
    monkeypatch.setenv("APP_DATA_MODE", "fixture")
    from app.shell.components.refresh_watch import current_in_flight

    assert current_in_flight({"CMP19_01"}) == frozenset()
