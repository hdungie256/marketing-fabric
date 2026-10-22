import pytest

from pipelines.dags.job_graph import job_graph
from pipelines.io.lineage import ROOT
from pipelines.jobs.platform.reload_plan.job import plan


def test_spend_reload_runs_ingest_then_only_its_descendants_in_order():
    graph = job_graph(ROOT)
    steps = plan("spend", graph)
    jobs = [s["job_id"] for s in steps]
    assert jobs[0] == "ingest/spend" and steps[0]["needs"] == []
    assert {"unified/campaign_spend", "marts/shared/campaign_spend", "marts/finance/budget_daily"} <= set(jobs)
    assert "ingest/sales" not in jobs and "unified/orders" not in jobs
    for i, step in enumerate(steps[1:], start=1):
        assert step["needs"] and set(step["needs"]) <= set(jobs[:i]), step  # each step waits for an earlier one
    assert all(s["scope"] == {"mode": "full"} for s in steps)


def test_unknown_source_is_rejected():
    with pytest.raises(KeyError, match="nope"):
        plan("nope", job_graph(ROOT))


def test_ingest_fails_with_the_injected_cause_before_extracting(monkeypatch):
    pytest.importorskip("pyspark")
    from pipelines.jobs.ingest import load

    monkeypatch.setattr(load, "active_fault", lambda source: "connection refused (test)")
    extracted = []
    with pytest.raises(ConnectionError, match="spend: connection refused"):
        load.run_ingest("ingest/spend", "spend", {"raw/spend/daily_spend": lambda: extracted.append(1)})
    assert extracted == []
