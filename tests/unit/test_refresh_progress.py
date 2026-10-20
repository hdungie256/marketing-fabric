from datetime import UTC, datetime, timedelta

import pandas as pd
import pytest

import fabric_control
from app.services import refresh_progress as rp

T0 = datetime(2026, 10, 20, 9, 0, tzinfo=UTC)
ITEMS = [
    ("unified/campaign_spend", "ingest/spend"),
    ("unified/campaign_spend", "unified/campaign_spend"),
    ("unified/daily_spend", "unified/campaign_spend"),
    ("mart_shared.campaign_spend_allocated", "marts/shared/campaign_spend"),
    ("mart_shared.spend_reconciliation", "marts/shared/campaign_spend"),
    ("mart_campaign.target_achievement", "marts/campaign/target_achievement"),
    ("mart_finance.budget_daily", "marts/finance/budget_daily"),
    ("mart_finance.contribution", "marts/finance/contribution"),
    ("mart_finance.contribution_sku", "marts/finance/contribution"),
]
# source plus 8 affected datasets
AFFECTED = [{"dataset_id": d, "job_id": j, "scope": {"mode": "full"}} for d, j in ITEMS]
EVENT = {"source": "spend", "keys": {"campaign_id": ["CMP26_01"]}}


@pytest.fixture(autouse=True)
def _patch(monkeypatch):
    monkeypatch.setattr(fabric_control, "affected_by", lambda event: AFFECTED)


def runs(*rows):
    return pd.DataFrame(rows, columns=["job_id", "event_id", "status"])


def test_steps_drop_source_and_keep_order():
    steps = rp.steps(EVENT)
    assert len(steps) == 8
    assert [s["label"] for s in steps][:2] == ["Spend source data", "Daily online spend"]


def test_datasets_of_one_job_share_status():
    st = rp.statuses(rp.steps(EVENT), runs(("unified/campaign_spend", "e1", "success")), "e1", T0, T0)
    assert st[:2] == ["done", "done"]
    assert st[2] == "queued"


def test_failed_job_marks_later_steps_skipped():
    steps = rp.steps(EVENT)
    r = runs(("unified/campaign_spend", "e1", "success"), ("marts/shared/campaign_spend", "e1", "failed"))
    st = rp.statuses(steps, r, "e1", T0, T0)
    assert st[2:4] == ["failed", "failed"]
    assert set(st[4:]) == {"skipped"}
    assert rp.finished(st) is True


def test_event_without_progress_times_out():
    st = rp.statuses(rp.steps(EVENT), runs(), "e1", T0, T0 + timedelta(seconds=601))
    assert set(st) == {"timed out"}
    assert rp.finished(st)


def _events():
    return pd.DataFrame(
        [
            {"event_id": "old", "emitted_at": T0, "keys": {"campaign_id": ["CMP26_01"]}, "dag_run_id": "d1", "source": "spend"},
            {"event_id": "new", "emitted_at": T0 + timedelta(minutes=5), "keys": '{"campaign_id": ["CMP26_01"]}', "dag_run_id": "d2", "source": "spend"},
        ]
    )


def test_in_flight_uses_latest_event_only():
    r = runs(("unified/campaign_spend", "old", "running"), ("unified/campaign_spend", "new", "success"),
             ("marts/shared/campaign_spend", "new", "running"))
    got = rp.in_flight(_events(), r, None, T0 + timedelta(minutes=6))
    assert got == frozenset({"mart_shared.campaign_spend_allocated", "mart_shared.spend_reconciliation",
                             "mart_campaign.target_achievement", "mart_finance.budget_daily",
                             "mart_finance.contribution", "mart_finance.contribution_sku"})


def test_in_flight_ignores_event_without_dag_run():
    ev = _events()
    ev.loc[1, "dag_run_id"] = None
    ev.loc[0, "dag_run_id"] = None
    assert rp.in_flight(ev, runs(), None, T0) == frozenset()


def test_in_flight_respects_campaign_selection():
    assert rp.in_flight(_events(), runs(), {"CMP19_01"}, T0 + timedelta(minutes=6)) == frozenset()
