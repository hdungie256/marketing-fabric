from datetime import UTC, datetime, timedelta

import pandas as pd

from app.services import demo_ready as dr

NOW = datetime(2026, 10, 27, 9, 0, tzinfo=UTC)
COLUMNS = ["run_id", "job_id", "event_id", "status", "started_at", "ended_at", "emitted_at"]


def at(minutes: float) -> datetime:
    return NOW + timedelta(minutes=minutes)


def runs(*rows):
    return pd.DataFrame(rows, columns=COLUMNS)


READY = runs(
    ("old:ingest/spend", "ingest/spend", None, "failed", at(-60), at(-59), None),
    ("full:ingest/spend", "ingest/spend", None, "success", at(-30), at(-28), None),
    ("full:ingest/crm", "ingest/crm", None, "success", at(-30), at(-29), None),
    ("full:marts/finance/budget_daily", "marts/finance/budget_daily", None, "success", at(-28), at(-25), None),
    ("evt:marts/finance/budget_daily", "marts/finance/budget_daily", "evt1", "success", at(-10), at(-9), at(-10)),
    # a test's fixed event_id reused across runs, no source change behind it: not a partial refresh
    ("t1:unified/y", "unified/y", "e2e-upsert", "success", at(-60), at(-59), None),
    ("t2:unified/y", "unified/y", "e2e-upsert", "success", at(-2), at(-1), None),
)
TIMINGS = pd.DataFrame({"page": ["overview", "overview"], "ms": [800.0, 1200.0]})


def test_ready_state_passes():
    checks = dr.state_checks(READY, [], [], []) + dr.timing_checks(READY, TIMINGS, NOW)
    assert all(ok for _, ok, _ in checks), checks


def test_latest_full_refresh_must_be_all_success():
    broken = pd.concat(
        [
            READY,
            runs(
                ("new:ingest/spend", "ingest/spend", None, "failed", at(-5), at(-4), None),
                ("new:ingest/crm", "ingest/crm", None, "success", at(-5), at(-4), None),
            ),
        ],
        ignore_index=True,
    )
    name, ok, detail = dr.full_refresh_check(broken)
    assert not ok and "ingest/spend failed" in detail
    assert not dr.full_refresh_check(runs())[1]


def test_stale_alerts_and_faults_fail():
    gated = pd.concat(
        [READY, runs(("full:unified/x", "unified/x", None, "gated", at(-26), at(-26), None))], ignore_index=True
    )
    checks = {name: ok for name, ok, _ in dr.state_checks(gated, ["unified/x"], ["source spend"], [])}
    assert checks == {
        "full refresh done": False,
        "all badges fresh": False,
        "alert count 0": False,
        "fault toggles off": False,
    }


def test_timings_over_target_or_missing_fail():
    slow = runs(
        ("full:a", "a", None, "success", at(-30), at(-15), None),
        ("evt:a", "a", "evt1", "success", at(-10), at(-7), at(-10)),
    )
    pages = pd.DataFrame({"page": ["overview"], "ms": [3500.0]})
    assert [ok for _, ok, _ in dr.timing_checks(slow, pages, NOW)] == [False, False, False]
    assert not any(ok for _, ok, _ in dr.timing_checks(runs(), pd.DataFrame(columns=["page", "ms"]), NOW))
