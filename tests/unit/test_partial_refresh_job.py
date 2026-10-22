import pytest

import fabric_control as fc
from pipelines.jobs.platform.partial_refresh import job

PLAN = [
    {"job_id": "ingest/spend", "scope": {"mode": "full"}, "needs": []},
    {"job_id": "unified/campaign_spend", "scope": {"mode": "scope"}, "needs": ["ingest/spend"]},
    {"job_id": "marts/finance/budget_daily", "scope": {"mode": "scope"}, "needs": ["unified/campaign_spend"]},
]


@pytest.fixture
def steps(monkeypatch):
    calls, cleared = [], []
    monkeypatch.setattr(fc, "affected_by", lambda event: [])
    monkeypatch.setattr(fc, "refresh_plan", lambda affected: PLAN)
    monkeypatch.setattr(job, "clear_cache", lambda: cleared.append(True))
    return calls, cleared


def test_runs_every_step_in_plan_order_in_one_process(monkeypatch, steps):
    calls, cleared = steps
    monkeypatch.setattr(job.refresh_step, "main", lambda job_id, scope, needs: calls.append(job_id))
    job.main({"source": "raw/spend/campaign_spend", "keys": {}})
    assert calls == [s["job_id"] for s in PLAN]
    assert len(cleared) == len(PLAN)


def test_failed_step_does_not_stop_the_loop_and_fails_the_task(monkeypatch, steps):
    calls, _ = steps

    def main(job_id, scope, needs):
        calls.append(job_id)
        if job_id == "unified/campaign_spend":
            raise RuntimeError("boom")
        if needs and "unified/campaign_spend" in needs:
            raise SystemExit(job.refresh_step.SKIPPED)

    monkeypatch.setattr(job.refresh_step, "main", main)
    with pytest.raises(SystemExit) as exit_:
        job.main({"source": "raw/spend/campaign_spend", "keys": {}})
    assert calls == [s["job_id"] for s in PLAN]
    assert str(exit_.value.code) == "did not succeed: unified/campaign_spend, marts/finance/budget_daily"
