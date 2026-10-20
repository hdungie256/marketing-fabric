import re
from contextlib import contextmanager, nullcontext
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest

import fabric_control as fc
from api.repositories import spend as repo
from api.services import spend

ROOT = Path(__file__).resolve().parents[2]
DAY = date(2019, 5, 20)


class Conn:
    def transaction(self):
        return nullcontext()


@pytest.fixture
def source(monkeypatch):
    state = {"rows": {("CMP19_03", DAY): Decimal("10")}, "version": 4, "triggered": [], "events": []}

    @contextmanager
    def connect():
        before = (dict(state["rows"]), state["version"])
        try:
            yield Conn()
        except Exception:
            state["rows"], state["version"] = before
            raise

    def update(conn, campaign_id, day, value):
        if (campaign_id, day) not in state["rows"]:
            return False
        state["rows"][(campaign_id, day)] = value
        return True

    def bump(conn, source):
        state["version"] += 1
        return state["version"]

    periods = {"CMP19_03": (date(2019, 5, 15), date(2019, 6, 10))}
    monkeypatch.setattr(repo, "connect", connect)
    monkeypatch.setattr(repo, "online_spend", lambda day: Decimal("100") if day == DAY else None)
    monkeypatch.setattr(repo, "lock_source", lambda conn, source: None)
    monkeypatch.setattr(repo, "campaign_period", lambda conn, campaign_id: periods.get(campaign_id))
    monkeypatch.setattr(repo, "other_allocations", lambda conn, campaign_id, day: Decimal("30"))
    monkeypatch.setattr(repo, "update_allocation", update)
    monkeypatch.setattr(repo, "bump_version", bump)
    monkeypatch.setattr(fc, "trigger", lambda dag_id, conf: state["triggered"].append((dag_id, conf)) or "dag-run-1")
    monkeypatch.setattr(fc, "record_event", lambda event, dag_run_id: state["events"].append((event, dag_run_id)))
    return state


def test_finance_controller_change_bumps_version_and_triggers_partial_refresh(source):
    result = spend.edit_allocation("UG04", "CMP19_03", DAY, Decimal("25"))
    event = result["event"]
    assert source["rows"][("CMP19_03", DAY)] == Decimal("25")
    assert event["source"] == "raw/spend/campaign_spend"
    assert event["keys"] == {"campaign_id": "CMP19_03", "date": "2019-05-20"}
    assert event["source_version"] == 5 and event["event_id"] and event["emitted_at"]
    assert source["triggered"] == [("partial_refresh", event)]
    assert source["events"] == [(event, "dag-run-1")]
    assert result["dag_run_id"] == "dag-run-1"


@pytest.mark.parametrize("role", ["UG01", "UG03", "UG06", "nobody"])
def test_other_roles_are_forbidden_with_reason(source, role):
    with pytest.raises(spend.Forbidden, match="raw/spend/campaign_spend"):
        spend.edit_allocation(role, "CMP19_03", DAY, Decimal("25"))
    assert source["version"] == 4 and source["triggered"] == []


@pytest.mark.parametrize(
    "campaign_id,day,value,field",
    [
        ("CMP19_03", DAY, Decimal("-1"), "allocated_online_spend"),
        ("CMP19_03", DAY, Decimal("100.01"), "allocated_online_spend"),
        ("CMP19_03", DAY, Decimal("70.01"), "allocated_online_spend"),
        ("CMP19_03", date(2019, 7, 1), Decimal("5"), "date"),
        ("CMP19_99", DAY, Decimal("5"), "campaign_id"),
    ],
)
def test_invariant_violations_name_the_field_and_change_nothing(source, campaign_id, day, value, field):
    with pytest.raises(spend.Invalid) as error:
        spend.edit_allocation("UG04", campaign_id, day, value)
    assert error.value.field == field and error.value.reason
    assert source["rows"][("CMP19_03", DAY)] == Decimal("10")
    assert source["version"] == 4 and source["triggered"] == []


def test_trigger_failure_keeps_event_and_reports(source, monkeypatch):
    monkeypatch.setattr(fc, "trigger", lambda dag_id, conf: (_ for _ in ()).throw(OSError("airflow down")))
    with pytest.raises(spend.RefreshNotStarted, match="airflow down"):
        spend.edit_allocation("UG04", "CMP19_03", DAY, Decimal("25"))
    assert source["events"][0][1] is None


def test_only_the_spend_api_triggers_partial_refresh():
    pattern = re.compile(r"trigger(_dag)?\(\s*[\"']partial_refresh")
    callers = [
        str(path.relative_to(ROOT))
        for path in ROOT.rglob("*.py")
        if not path.is_relative_to(ROOT / "tests") and pattern.search(path.read_text())
    ]
    assert callers == ["api/services/spend.py"]


def test_router_maps_errors_to_status(source):
    pytest.importorskip("fastapi")
    pytest.importorskip("httpx")
    from fastapi.testclient import TestClient

    from api.main import app

    client = TestClient(app)
    url = "/spend/campaign_spend/CMP19_03/2019-05-20"
    assert client.put(url, json={"allocated_online_spend": 5}, headers={"X-Fabric-Role": "UG03"}).status_code == 403
    invalid = client.put(url, json={"allocated_online_spend": -1}, headers={"X-Fabric-Role": "UG04"})
    assert invalid.status_code == 422 and invalid.json()["detail"]["field"] == "allocated_online_spend"
    ok = client.put(url, json={"allocated_online_spend": 5}, headers={"X-Fabric-Role": "UG04"})
    assert ok.status_code == 200 and ok.json()["dag_run_id"] == "dag-run-1"
