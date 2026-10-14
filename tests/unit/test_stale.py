from datetime import UTC, datetime

import pytest
import yaml
from streamlit.testing.v1 import AppTest

import fabric_control as fc
from fabric_control import data_quality, refresh
from fabric_control.clients import postgres
from fabric_control.models import DataQualityResult, GateFailed, RuleResult

JOBS = {
    "ingest/sales": ([], ["raw/sales/lines"]),
    "unified/orders": (["raw/sales/lines"], ["unified/orders", "unified/order_issues"]),
    "unified/customers": (["raw/sales/lines"], ["unified/customers"]),
    "marts/shared/overview": (["unified/orders"], ["mart_shared.overview"]),
}
GATED_AT = datetime(2026, 10, 14, 9, 0, tzinfo=UTC)


@pytest.fixture
def online(monkeypatch, tmp_path):
    entries = []
    for job_id, (inputs, outputs) in JOBS.items():
        job = tmp_path / "jobs" / job_id / "job.py"
        job.parent.mkdir(parents=True, exist_ok=True)
        job.write_text(f"INPUTS = {inputs!r}\nOUTPUTS = {outputs!r}\n")
        for dataset_id in outputs:
            entry = {"dataset_id": dataset_id, "om_fqn": dataset_id, "openlineage": {}, "job_id": job_id, "tags": []}
            entries.append(entry | ({"natural_key": ["id"]} if dataset_id.startswith("raw/") else {}))
    (tmp_path / "datasets").mkdir()
    (tmp_path / "datasets" / "a.yml").write_text(yaml.safe_dump({"datasets": entries}))
    monkeypatch.setenv("FABRIC_CONTRACTS_DIR", str(tmp_path))
    monkeypatch.setenv("FABRIC_JOBS_DIR", str(tmp_path / "jobs"))
    monkeypatch.setenv("FABRIC_CONTROL_MODE", "online")
    refresh.lineage_graph.cache_clear()
    runs = []
    monkeypatch.setattr(postgres, "gated_runs", lambda: runs)
    return runs


def test_offline_status_is_fresh(monkeypatch):
    monkeypatch.setenv("FABRIC_CONTROL_MODE", "offline")
    assert fc.status("unified/orders") == {"stale": False, "since": None, "cause": None, "datasets": []}


def test_gated_dataset_and_descendants_are_stale(online):
    online.append(("unified/orders", GATED_AT, "orders_unique", ["unified/orders"]))
    for dataset_id in ("unified/orders", "mart_shared.overview"):
        state = fc.status(dataset_id)
        assert state["stale"] is True
        assert state["since"] == GATED_AT
        assert state["cause"] == "quality check failed on `unified/orders`"
        assert state["datasets"] == ["unified/orders"]
    for dataset_id in ("raw/sales/lines", "unified/customers", "unified/order_issues"):
        assert fc.status(dataset_id)["stale"] is False


def test_gate_without_quality_rows_marks_every_output(online):
    online.append(("unified/orders", GATED_AT, "reconcile", []))
    assert fc.status("unified/order_issues")["stale"] is True


def test_upstream_gate_lists_every_failed_dataset(online):
    online.append(("ingest/sales", datetime(2026, 10, 14, 8, 0, tzinfo=UTC), None, []))
    online.append(("unified/orders", GATED_AT, None, ["unified/orders"]))
    state = fc.status("mart_shared.overview")
    assert state["datasets"] == ["raw/sales/lines", "unified/orders"]
    assert state["since"] == datetime(2026, 10, 14, 8, 0, tzinfo=UTC)


def test_no_gated_runs_is_fresh(online):
    assert fc.status("mart_shared.overview")["stale"] is False


def test_unknown_dataset_raises(online):
    with pytest.raises(KeyError):
        fc.status("unified/nope")


def test_database_down_reports_fresh(online, monkeypatch):
    def down():
        raise OSError("pg down")

    monkeypatch.setattr(postgres, "gated_runs", down)
    assert fc.status("unified/orders")["stale"] is False


def test_gate_carries_failing_rules():
    rules = [RuleResult("orders_unique", "critical", False), RuleResult("amount_range", "warning", False)]
    with pytest.raises(GateFailed) as raised:
        fc.gate(DataQualityResult("unified/orders", {"mode": "full"}, rules))
    assert raised.value.rules == ["orders_unique"]


def test_gated_run_records_failing_rule(monkeypatch):
    monkeypatch.setenv("FABRIC_CONTROL_MODE", "online")
    ended = []
    monkeypatch.setattr(postgres, "start_run", lambda *a: None)
    monkeypatch.setattr(postgres, "add_alert", lambda *a: None)
    monkeypatch.setattr(postgres, "end_run", lambda run_id, status, *rest: ended.append((status, rest[2])))
    with pytest.raises(GateFailed), fc.run("unified/orders", {"mode": "full"}):
        raise GateFailed("unified/orders: critical rules failed", ["orders_unique", "order_key_not_null"])
    assert ended == [("gated", "orders_unique, order_key_not_null")]


def test_break_dq_injects_critical_failure(monkeypatch):
    monkeypatch.setenv("FABRIC_CONTROL_MODE", "online")
    monkeypatch.setattr(postgres, "dq_breaks", lambda: {"unified/orders"})
    [rule] = data_quality.injected("unified/orders")
    assert (rule.rule_id, rule.severity, rule.passed) == ("break_dq", "critical", False)
    assert data_quality.injected("unified/customers") == []
    monkeypatch.setenv("FABRIC_CONTROL_MODE", "offline")
    assert data_quality.injected("unified/orders") == []


def test_break_dq_rejects_unregistered_dataset(monkeypatch):
    monkeypatch.setattr(postgres, "set_dq_break", lambda *a: pytest.fail("should not write"))
    with pytest.raises(KeyError):
        data_quality.break_dq("unified/nope")


def _stale_page():
    from datetime import UTC, datetime

    import streamlit as st

    from app.shell import metric, session
    from app.shell.page import wrap
    from app.shell.registry import PageSpec

    def render():
        at = datetime(2026, 10, 14, 9, 0, tzinfo=UTC)
        metric("attributed_orders", 1290, at)
        metric("attributed_buyers", 870, at)
        metric("campaign_budget", 5, at)

    session.set_role("UG01")
    wrap(PageSpec("campaign_overview", "Campaign Overview", "Campaigns", render, frozenset({"UG01"})))()
    st.text("done")


def test_stale_metrics_and_one_banner(monkeypatch):
    terms = {
        "attributed_orders": {"display_name": "Attributed Orders", "dataset_id": "mart_shared.overview"},
        "attributed_buyers": {"display_name": "Attributed Buyers", "dataset_id": "mart_shared.overview"},
        "campaign_budget": {"display_name": "Campaign Budget", "dataset_id": "unified/campaigns"},
    }
    stale = {"stale": True, "since": GATED_AT, "cause": "c", "datasets": ["unified/orders"]}
    fresh = {"stale": False, "since": None, "cause": None, "datasets": []}
    monkeypatch.setattr(fc, "term", lambda term_id: {"notes": [], "synthetic": False} | terms[term_id])
    monkeypatch.setattr(fc, "status", lambda d: stale if d == "mart_shared.overview" else fresh)
    monkeypatch.setattr(fc, "record_timing", lambda page, ms: None)
    at = AppTest.from_function(_stale_page).run()
    assert not at.exception
    assert [w.value for w in at.warning] == ["Using previous version — quality check failed on `unified/orders`"]
    badges = [m.value for m in at.markdown if "Using previous version" in m.value or "Refreshed" in m.value]
    assert sum("Using previous version" in b for b in badges) == 2
    assert sum("Refreshed" in b for b in badges) == 1
