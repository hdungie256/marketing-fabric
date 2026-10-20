import runpy

import pytest

import fabric_control as fc
from fabric_control.clients import postgres
from pipelines.jobs.platform.refresh_step import job


def test_blocked_lists_needs_without_success_in_this_dag_run(monkeypatch):
    monkeypatch.setenv("FABRIC_CONTROL_MODE", "online")
    monkeypatch.setenv("FABRIC_DAG_RUN_ID", "dag1")
    monkeypatch.setattr(postgres, "run_statuses", lambda ids: {"dag1:a": "success", "dag1:b": "gated"})
    assert fc.blocked(["a", "b", "c"]) == ["b", "c"]
    assert fc.blocked([]) == []


def test_step_skips_when_upstream_did_not_succeed(monkeypatch):
    monkeypatch.setattr(fc, "blocked", lambda needs: ["marts/shared/campaign_spend"])
    monkeypatch.setattr(runpy, "run_module", lambda *a, **k: pytest.fail("job ran"))
    with pytest.raises(SystemExit) as exit_:
        job.main("marts/finance/budget_daily", {"mode": "full"}, ["marts/shared/campaign_spend"])
    assert exit_.value.code == job.SKIPPED


def test_step_runs_job_module_with_scope(monkeypatch):
    calls = []
    monkeypatch.setattr(fc, "blocked", lambda needs: [])
    monkeypatch.setattr(runpy, "run_module", lambda name, **kwargs: calls.append((name, list(job.sys.argv))))
    job.main("marts/finance/budget_daily", {"mode": "scope", "keys": {"campaign_id": ["C1"]}}, [])
    assert calls == [
        (
            "pipelines.jobs.marts.finance.budget_daily.job",
            ["marts/finance/budget_daily", "--scope", '{"mode": "scope", "keys": {"campaign_id": ["C1"]}}'],
        )
    ]
