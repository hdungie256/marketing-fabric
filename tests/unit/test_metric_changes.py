from decimal import Decimal

import pytest

import fabric_control as fc
from fabric_control import changes
from fabric_control.clients import postgres


def test_diff_reports_changed_added_and_removed_metrics_only():
    before = [
        {"campaign_id": "C1", "allocated": Decimal("10.00"), "orders": 3},
        {"campaign_id": "C2", "allocated": Decimal("5.00"), "orders": 1},
    ]
    after = [
        {"campaign_id": "C1", "allocated": Decimal("12.50"), "orders": 3},
        {"campaign_id": "C3", "allocated": Decimal("1.00"), "orders": 0},
    ]
    assert changes.diff(["campaign_id"], ["allocated", "orders"], before, after) == [
        ({"campaign_id": "C1"}, "allocated", Decimal("10.00"), Decimal("12.50")),
        ({"campaign_id": "C2"}, "allocated", Decimal("5.00"), None),
        ({"campaign_id": "C2"}, "orders", 1, None),
        ({"campaign_id": "C3"}, "allocated", None, Decimal("1.00")),
        ({"campaign_id": "C3"}, "orders", None, 0),
    ]


def test_equal_decimals_are_unchanged():
    row = {"campaign_id": "C1", "allocated": Decimal("10.00")}
    assert changes.diff(["campaign_id"], ["allocated"], [row], [{**row, "allocated": Decimal("10")}]) == []


def test_restricted_metrics_are_not_logged_for_wider_readers():
    assert changes.visible("mart_finance.contribution", ["campaign_cost", "estimated_contribution"]) == [
        "campaign_cost"
    ]
    assert changes.visible("mart_finance.contribution_sku", ["quantity", "reference_cogs"]) == ["quantity"]


def test_metric_changes_use_glossary_term_ids():
    before = [{"campaign_id": "C1", "date": "2019-01-15", "allocated": Decimal("10.00")}]
    after = [{"campaign_id": "C1", "date": "2019-01-15", "allocated": Decimal("12.00")}]
    [(key, term_id, was, now)] = changes.metric_changes("mart_shared.campaign_spend_allocated", before, after)
    assert key == {"campaign_id": "C1", "date": "2019-01-15"}
    assert term_id == changes.term_for("mart_shared.campaign_spend_allocated", "allocated", fc.glossary.load_terms())
    assert (was, now) == (Decimal("10.00"), Decimal("12.00"))


def test_record_change_writes_log_with_event(monkeypatch):
    monkeypatch.setenv("FABRIC_CONTROL_MODE", "online")
    monkeypatch.setenv("FABRIC_EVENT_ID", "e1")
    for name in ("start_run", "end_run"):
        monkeypatch.setattr(postgres, name, lambda *a: None)
    logged = []
    monkeypatch.setattr(postgres, "insert_metric_changes", lambda *a: logged.append(a))
    before = [{"campaign_id": "C1", "allocated": Decimal("1")}]
    after = [{"campaign_id": "C1", "allocated": Decimal("2")}]
    monkeypatch.setattr(changes, "load_manifests", lambda: {"d": {"grain": ["campaign_id"], "metrics": ["allocated"]}})
    monkeypatch.setattr(changes, "visible", lambda dataset_id, columns: columns)
    with fc.run("marts/x", {"mode": "scope", "keys": {"campaign_id": ["C1"]}}) as run:
        assert run.record_change("d", before, after) == 1
    [(run_id, event_id, dataset_id, rows)] = logged
    assert (event_id, dataset_id) == ("e1", "d")
    assert rows == [({"campaign_id": "C1"}, "allocated", Decimal("1"), Decimal("2"))]


def test_record_change_offline_does_nothing(monkeypatch):
    monkeypatch.setattr(postgres, "insert_metric_changes", lambda *a: pytest.fail("database used offline"))
    with fc.run("marts/x", {"mode": "full"}) as run:
        assert run.record_change("d", [], []) == 0
