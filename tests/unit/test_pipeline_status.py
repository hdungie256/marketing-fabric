from datetime import UTC, datetime, timedelta

import pandas as pd
import pytest
from streamlit.testing.v1 import AppTest

from app.pages.ops import pipeline_status as page
from app.services import pipeline_status as ps

NOW = datetime(2026, 10, 19, 10, 0, tzinfo=UTC)
RUN_COLUMNS = [
    "run_id",
    "job_id",
    "event_id",
    "status",
    "started_at",
    "ended_at",
    "rows_in",
    "rows_out",
    "failing_step",
]


def at(minutes: float) -> datetime:
    return NOW + timedelta(minutes=minutes)


def runs(*rows):
    return pd.DataFrame(rows, columns=RUN_COLUMNS)


RUNS = runs(
    ("r1", "ingest/spend", None, "success", at(-30), at(-29), 365, 365, None),
    ("r2", "ingest/spend", None, "failed", at(-10), at(-9.5), 365, 0, "read_api spend.campaign_spend"),
    ("r3", "unified/campaign_spend", None, "gated", at(-9), at(-8.9), 0, 0, "gate"),
    ("r4", "marts/finance/budget_daily", "evt1", "success", at(-5), at(-4), 10, 10, None),
    ("r5", "marts/finance/contribution", "evt1", "success", at(-4), at(-2), 10, 10, None),
)
ALERTS = pd.DataFrame(
    [("r2", "critical", "TimeoutError: spend API unreachable", at(-9.5))],
    columns=["run_id", "severity", "message", "raised_at"],
)
TIMINGS = pd.DataFrame(
    [("budget_spend", ms, at(-1)) for ms in (800, 900, 1000, 4000)], columns=["page", "ms", "recorded_at"]
)
RECON = pd.DataFrame(
    [("l1", "raw/spend/daily_spend", 365, 365, 365, True, None, at(-29))],
    columns=["load_id", "dataset_id", "source_rows", "raw_rows", "baseline_rows", "passed", "reason", "checked_at"],
)


def test_latest_run_per_job_with_cause_only_when_broken():
    latest = ps.latest_runs(RUNS, ALERTS, NOW).set_index("job_id")
    assert latest.loc["ingest/spend", "status"] == "failed"
    assert latest.loc["ingest/spend", "cause"] == "TimeoutError: spend API unreachable"
    assert latest.loc["ingest/spend", "duration_s"] == 30
    assert latest.loc["marts/finance/budget_daily", "cause"] == ""


def test_running_job_duration_counts_to_now():
    running = runs(("r9", "ingest/sales", None, "running", at(-2), None, None, None, None))
    assert ps.latest_runs(running, None, NOW)["duration_s"].iloc[0] == 120
    assert ps.is_active(running) and not ps.is_active(RUNS)


def test_event_elapsed_from_first_start_to_last_end():
    chosen, elapsed = ps.event_runs(RUNS, "evt1", NOW)
    assert list(chosen["job_id"]) == ["marts/finance/budget_daily", "marts/finance/contribution"]
    assert elapsed == 180 and elapsed > ps.TARGET_SECONDS
    assert ps.event_runs(RUNS, "missing", NOW)[1] is None


@pytest.mark.parametrize("value,text", [(None, "—"), (5, "0:05"), (125.4, "2:05")])
def test_fmt_duration(value, text):
    assert ps.fmt_duration(value) == text


def _script():
    from app.shell import session
    from app.shell.page import wrap
    from app.shell.registry import load_pages

    session.set_role("UG06")
    wrap(next(p for p in load_pages() if p.key == "pipeline_status"))()


def run_page(monkeypatch, data, event_id=None, status=None):
    monkeypatch.setattr(page, "load", lambda: data)
    app = AppTest.from_function(_script)
    if event_id:
        app.query_params["event_id"] = event_id
    if status:
        app.query_params["status"] = status
    return app.run()


def test_page_shows_failed_step_cause_and_banner(monkeypatch):
    app = run_page(monkeypatch, (RUNS, ALERTS, RECON, TIMINGS))
    assert not app.exception, app.exception
    captions = " ".join(c.value for c in app.caption)
    assert "Failed at read_api spend.campaign_spend — TimeoutError: spend API unreachable" in captions
    assert "2 step(s) failed or gated" in app.warning[0].value
    assert "Auto-refreshes" not in captions
    assert len(app.dataframe) == 1


def test_event_link_shows_elapsed_and_over_target(monkeypatch):
    app = run_page(monkeypatch, (RUNS, ALERTS, RECON, TIMINGS), event_id="evt1")
    assert not app.exception, app.exception
    text = " ".join(m.value for m in app.markdown)
    assert "3:00 elapsed · 2:00 target" in text


def test_active_run_mentions_auto_refresh(monkeypatch):
    running = pd.concat([RUNS, runs(("r9", "ingest/sales", None, "running", at(-1), None, None, None, None))])
    app = run_page(monkeypatch, (running, ALERTS, RECON, TIMINGS))
    assert any("Auto-refreshes every 5s" in c.value for c in app.caption)


def test_registered_as_data_ops_home():
    from app.shell.registry import load_pages, validate

    pages = load_pages()
    validate(pages)
    spec = next(p for p in pages if p.key == "pipeline_status")
    assert spec.roles == spec.home_for == frozenset({"UG06"})


def test_alert_count_is_role_specific():
    assert ps.alert_count(RUNS, "UG06") == 1  # ingest/spend failed
    assert ps.alert_count(RUNS, "UG05") == 1  # unified/campaign_spend gated
    assert ps.alert_count(RUNS, "UG01") == 0
    recovered = pd.concat([RUNS, runs(("r6", "ingest/spend", None, "success", at(-1), at(-0.5), 365, 365, None))])
    assert ps.alert_count(recovered, "UG06") == 0


def test_full_refresh_wall_time_uses_newest_dag_run():
    full = runs(
        ("old:ingest/sales", "ingest/sales", None, "success", at(-60), at(-59), 1, 1, None),
        ("new:ingest/sales", "ingest/sales", None, "success", at(-20), at(-19), 1, 1, None),
        ("new:marts/x", "marts/x", None, "success", at(-18), at(-8), 1, 1, None),
    )
    assert ps.last_full_refresh_seconds(full, NOW) == 720


def test_event_latency_and_page_percentiles():
    assert ps.event_latencies(RUNS, NOW).to_dict("records") == [{"event_id": "evt1", "seconds": 180.0}]
    row = ps.page_percentiles(TIMINGS).iloc[0]
    assert (row["page"], row["p50_ms"], row["samples"]) == ("budget_spend", 950.0, 4)
    assert row["p95_ms"] > ps.PAGE_TARGET_MS


def test_failed_filter_and_performance_chips(monkeypatch):
    app = run_page(monkeypatch, (RUNS, ALERTS, RECON, TIMINGS), status="failed")
    assert not app.exception, app.exception
    jobs = [m.value for m in app.markdown if m.value.startswith("`ingest") or m.value.startswith("`marts")]
    assert jobs == ["`ingest/spend`"]
    text = " ".join(m.value for m in app.markdown)
    assert "Partial refresh `evt1`" in text and "Page `budget_spend`" in text


def _indicator(count):
    import streamlit as st

    from app.pages.ops import alerts

    alerts.count = lambda role: count
    page = st.Page(lambda: None, title="Pipeline Status", url_path="pipeline_status")
    alerts.alert_indicator("UG06", {"pipeline_status": page})
    alerts.alert_indicator("UG01", {"pipeline_status": page})


@pytest.mark.parametrize("count,links", [(2, ["2 open pipeline alerts"]), (0, [])])
def test_alert_indicator_hidden_at_zero_and_for_other_roles(count, links):
    app = AppTest.from_function(_indicator, args=(count,)).run()
    assert not app.exception, app.exception
    assert [link.label for link in app.get("page_link")] == links


def test_sources_and_reload_targets(monkeypatch):
    import fabric_control

    calls = []
    monkeypatch.setattr(fabric_control, "trigger", lambda dag_id, conf: calls.append((dag_id, conf)) or "run-1")
    assert ps.sources(RUNS) == ["spend"]
    assert ps.reload("spend") == "run-1" and ps.reload(None) == "run-1"
    assert calls == [("reload_source", {"source": "spend"}), ("full_refresh", {})]


@pytest.mark.parametrize(
    "choice,error,expected",
    [
        ("spend", None, [("reload_source", {"source": "spend"})]),
        ("Whole pipeline", None, [("full_refresh", {})]),
        ("spend", 404, []),
    ],
)
def test_reload_asks_once_then_triggers(monkeypatch, choice, error, expected):
    import fabric_control
    from fabric_control.clients.http import HttpError

    calls = []

    def trigger(dag_id, conf):
        if error:
            raise HttpError("POST", "/dags", error, "")
        calls.append((dag_id, conf))
        return "run-1"

    monkeypatch.setattr(fabric_control, "trigger", trigger)
    app = run_page(monkeypatch, (RUNS, ALERTS, RECON, TIMINGS))
    app.selectbox(key="reload-source").set_value(choice).run()
    app.button(key="reload-start").click().run()
    assert calls == []  # nothing starts before confirming
    app.button(key="reload-confirm").click().run()
    assert calls == expected
    if error:
        assert "not deployed" in app.error[0].value


def test_event_latency_starts_at_emitted_at():
    emitted = RUNS[RUNS["event_id"] == "evt1"]["started_at"].min() - pd.Timedelta(seconds=20)
    events = pd.DataFrame([{"event_id": "evt1", "emitted_at": emitted}])
    runs = ps.with_emitted_at(RUNS, events)
    assert ps.event_latencies(runs, NOW).to_dict("records") == [{"event_id": "evt1", "seconds": 200.0}]
