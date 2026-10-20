from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pandas as pd
import pytest

from app.services import change_history as ch
from fabric_control.glossary import load_terms

T0 = datetime(2026, 10, 20, 10, 42, tzinfo=UTC)
D = "2019-11-12"
CD = {"campaign_id": "CMP19_05", "date": D}
EVENT = {
    "event_id": "e1",
    "emitted_at": T0,
    "source": "raw/spend/campaign_spend",
    "keys": {"campaign_id": "CMP19_05", "date": D},
    "source_version": 8,
    "dag_run_id": "d1",
}
# The spec's "Change-log rows" table: what 8.3 writes for the demo edit, term_ids as logged.
LOG_ROWS = [
    ("mart_shared.campaign_spend_allocated", CD, "allocated_spend", "1356.33", "1156.33"),
    (
        "mart_finance.budget_daily",
        '{"campaign_id": "CMP19_05", "date": "2019-11-12"}',
        "cost_per_attributed_order",
        "1356.33",
        "1156.33",
    ),
    ("mart_shared.spend_reconciliation", {"date": D}, "allocated", "1356.33", "1156.33"),
    ("mart_shared.spend_reconciliation", {"date": D}, "unallocated_spend", "2034.49", "2234.49"),
    ("mart_campaign.target_achievement", {"campaign_id": "CMP19_05"}, "allocated_spend", "24593.53", "24393.53"),
    ("mart_finance.contribution", {"campaign_id": "CMP19_05"}, "campaign_cost", "24593.53", "24393.53"),
]


def log(rows=LOG_ROWS):
    return pd.DataFrame(
        [
            {
                "event_id": "e1",
                "dataset_id": d,
                "grain_key": g,
                "term_id": t,
                "old_value": Decimal(o),
                "new_value": Decimal(n),
            }
            for d, g, t, o, n in rows
        ]
    )


def runs():
    def run(job, n, before=None, after=None):
        return {
            "run_id": f"d1:{job}",
            "job_id": job,
            "event_id": "e1",
            "status": "success",
            "started_at": T0 + timedelta(seconds=n),
            "ended_at": T0 + timedelta(seconds=n + 10),
            "delta_version_before": before,
            "delta_version": after,
        }

    return pd.DataFrame(
        [
            run("ingest/spend", 0),
            run("unified/campaign_spend", 10, 41, 42),
            run("marts/shared/campaign_spend", 20, 5, 6),
            run("marts/campaign/target_achievement", 30),
            run("marts/finance/budget_daily", 40),
            run("marts/finance/contribution", 62),
        ]
    )


def test_column_of_recovers_mislabelled_budget_daily_row():
    assert ch.column_of("mart_finance.budget_daily", "cost_per_attributed_order", load_terms()) == "allocated"
    assert ch.column_of("mart_finance.contribution", "campaign_cost", load_terms()) == "campaign_cost"


def test_changed_values_groups_demo_log_into_four_rows():
    got = ch.changed_values(log(), EVENT, load_terms())
    assert list(got.columns) == ["metric", "info_term", "level", "page", "old", "new", "change"]
    assert list(got["metric"]) == ["Allocated spend", "Unallocated spend", "Allocated spend", "Campaign cost"]
    assert list(got["level"]) == ["CMP19_05 · 2019-11-12", "2019-11-12", "Campaign total", "Campaign total"]
    assert list(got["change"]) == pytest.approx([-200, 200, -200, -200])
    assert list(got["page"]) == ["budget_spend", "budget_spend", "targets", "contribution"]
    # ⓘ only where a glossary term defines the value: not the Targets campaign total.
    assert list(got["info_term"]) == ["allocated_spend", "unallocated_spend", None, None]


def test_rows_with_different_values_are_not_merged():
    rows = list(LOG_ROWS)
    rows[1] = (*rows[1][:3], "1356.33", "1000.00")  # budget_daily disagrees with campaign_spend_allocated
    rows[2] = (*rows[2][:3], "1356.33", "1100.00")  # reconciliation disagrees too
    got = ch.changed_values(log(rows), EVENT, load_terms())
    assert len(got) == 6
    assert list(got["level"][:3]) == ["CMP19_05 · 2019-11-12", "2019-11-12", "2019-11-12"]


def _frame(times, cols=("allocated",)):
    return pd.DataFrame({**{c: [1.0] * len(times) for c in cols}, "_refreshed_at": times})


def test_kept_counts_rows_before_emitted_at():
    old, older = T0 - timedelta(hours=1), T0 - timedelta(hours=2)
    frames = {
        "mart_shared.campaign_spend_allocated": _frame([older, old, T0 + timedelta(seconds=30)]),
        "mart_shared.spend_reconciliation": _frame([older], cols=("allocated", "unallocated")),
    }
    metrics = {
        "mart_shared.campaign_spend_allocated": ["allocated"],
        "mart_shared.spend_reconciliation": ["allocated", "unallocated", "online_spend"],
    }
    assert ch.kept(frames, metrics, T0) == (4, old)


def test_kept_skips_unreadable_datasets():
    frames = {"mart_finance.contribution": None, "mart_shared.campaign_spend_allocated": _frame([T0 - timedelta(1)])}
    metrics = {"mart_finance.contribution": ["campaign_cost"], "mart_shared.campaign_spend_allocated": ["allocated"]}
    assert ch.kept(frames, metrics, T0) == (1, T0 - timedelta(1))
    assert isinstance(ch.kept(frames, metrics, T0)[1], datetime)  # the page formats it with fmt_time
    assert ch.kept({"x": None}, {"x": ["a"]}, T0) == (0, None)


@pytest.fixture(autouse=True)
def _tz(monkeypatch):
    monkeypatch.setenv("APP_TZ", "Asia/Ho_Chi_Minh")  # UTC+7: times must be shown in APP_TZ, not UTC


def test_flow_columns_and_chips():
    cols = dict(ch.flow(EVENT, runs(), log()))
    assert list(cols) == ["Source", "Unified", "Shared marts", "Page marts"]
    assert len(cols["Shared marts"]) == 2
    nodes = {n["dataset_id"]: n for col in cols.values() for n in col}
    assert nodes["raw/spend/campaign_spend"]["meta"] == "Source version 7 → 8"
    assert nodes["raw/spend/campaign_spend"]["chip"] == ("info", "Edited")
    assert nodes["unified/campaign_spend"]["meta"] == "Delta version 41 → 42"
    assert nodes["unified/daily_spend"]["meta"] == "Refreshed 17:42"
    assert nodes["unified/daily_spend"]["chip"] == ("neutral", "Recomputed, no tracked change")
    assert nodes["mart_shared.spend_reconciliation"]["label"] == "Daily spend reconciliation"
    assert nodes["mart_shared.spend_reconciliation"]["chip"] == ("info", "2 changed")
    assert nodes["mart_shared.spend_reconciliation"]["meta"] == "Refreshed 17:42"
    assert nodes["mart_shared.spend_reconciliation"]["page"] is None
    assert nodes["mart_finance.contribution"]["meta"] == "Refreshed 17:43"
    assert nodes["mart_finance.contribution"]["page"] == "contribution"
    assert nodes["mart_finance.contribution_sku"]["chip"] == ("neutral", "Recomputed, no tracked change")


def test_not_downstream_lists_other_marts():
    got = ch.not_downstream(EVENT)
    assert "RFM" in got and got == sorted(got)
    assert "Targets" not in got and "Daily spend reconciliation" not in got


def test_event_table_change_text():
    events = pd.DataFrame([{k: v for k, v in EVENT.items()}])
    events.loc[0, "keys"] = '{"campaign_id": "CMP19_05", "date": "2019-11-12"}'
    got = ch.event_table(events, runs(), log())
    assert list(got.columns) == [
        "event_id",
        "saved_at",
        "change",
        "campaign_id",
        "datasets",
        "values_changed",
        "refresh_seconds",
    ]
    row = got.iloc[0]
    assert row["change"] == "Allocated spend for 2019-11-12 set to 1,156.33"
    assert (row["campaign_id"], row["datasets"], row["values_changed"], row["refresh_seconds"]) == (
        "CMP19_05",
        8,
        4,
        72,
    )
    assert ch.event_table(events, runs(), log()[0:0]).iloc[0]["change"] == "Allocated spend for 2019-11-12 changed"


def test_flow_without_version_before_falls_back_to_refreshed():
    r = runs()
    r.loc[r["job_id"] == "unified/campaign_spend", "delta_version_before"] = None
    nodes = {n["dataset_id"]: n for _, col in ch.flow(EVENT, r, log()) for n in col}
    assert nodes["unified/campaign_spend"]["meta"] == "Refreshed 17:42"


def test_functions_accept_json_string_keys():
    event = {**EVENT, "keys": '{"campaign_id": "CMP19_05", "date": "2019-11-12"}'}
    assert len(ch.changed_values(log(), event, load_terms())) == 4
    assert len(dict(ch.flow(event, runs(), log()))["Page marts"]) == 4
    assert ch.not_downstream(event) == ch.not_downstream(EVENT)
