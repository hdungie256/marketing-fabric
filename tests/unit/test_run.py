import pytest

import fabric_control as fc
from fabric_control.clients import postgres
from fabric_control.models import GateFailed


@pytest.fixture
def ops(monkeypatch):
    calls = {"start": [], "end": [], "alert": []}
    monkeypatch.setenv("FABRIC_CONTROL_MODE", "online")
    monkeypatch.setenv("FABRIC_DAG_RUN_ID", "dag1")
    monkeypatch.setattr(postgres, "start_run", lambda *a: calls["start"].append(a))
    monkeypatch.setattr(postgres, "end_run", lambda *a: calls["end"].append(a))
    monkeypatch.setattr(postgres, "add_alert", lambda *a: calls["alert"].append(a))
    return calls


def test_success_records_counts(ops):
    with fc.run("ingest/sales", {"mode": "full"}) as run:
        run.rows_in, run.rows_out, run.delta_version = 5, 5, 3
    assert ops["start"] == [("dag1:ingest/sales", "ingest/sales", None, {"mode": "full"})]
    assert ops["end"] == [("dag1:ingest/sales", "success", 5, 5, None, 3, None)]
    assert ops["alert"] == []


def test_failure_records_step_and_alert(ops):
    with pytest.raises(RuntimeError), fc.run("ingest/sales", {"mode": "full"}) as run:
        run.step = "append_raw raw/sales/lines"
        raise RuntimeError("boom")
    assert ops["end"][0][1:] == ("failed", None, None, "append_raw raw/sales/lines", None, None)
    assert ops["alert"] == [("dag1:ingest/sales", "ingest/sales", "critical", "RuntimeError: boom")]


def test_gate_failure_is_gated(ops):
    with pytest.raises(GateFailed), fc.run("unified/orders", {"mode": "full"}):
        raise GateFailed("critical rules failed")
    assert ops["end"][0][1] == "gated"
    assert ops["alert"][0][2] == "warning"


def test_offline_run_does_not_touch_database(monkeypatch):
    monkeypatch.setattr(postgres, "start_run", lambda *a: pytest.fail("database used offline"))
    with fc.run("ingest/sales", {"mode": "full"}) as run:
        assert run.run_id.endswith(":ingest/sales")
