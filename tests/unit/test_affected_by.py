import pytest
import yaml

import fabric_control as fc
from fabric_control.manifests import ManifestError, load_manifests

JOBS = {
    "ingest/spend": ([], ["raw/spend/campaign_spend", "raw/spend/daily_spend"]),
    "ingest/sales": ([], ["raw/sales/lines"]),
    "unified/campaigns": (["raw/sales/lines"], ["unified/campaigns"]),
    "unified/orders": (["raw/sales/lines"], ["unified/orders"]),
    "unified/campaign_spend": (
        ["raw/spend/campaign_spend", "raw/spend/daily_spend", "unified/campaigns"],
        ["unified/campaign_spend", "unified/daily_spend"],
    ),
    "marts/shared/campaign_spend": (
        ["unified/campaign_spend", "unified/daily_spend"],
        ["mart_shared.campaign_spend_allocated", "mart_shared.spend_reconciliation"],
    ),
    "marts/finance/budget_daily": (["mart_shared.campaign_spend_allocated"], ["mart_finance.budget_daily"]),
    "marts/finance/contribution": (["mart_shared.campaign_spend_allocated"], ["mart_finance.contribution"]),
    "marts/campaign/target_achievement": (
        ["mart_shared.campaign_spend_allocated", "unified/campaigns"],
        ["mart_campaign.target_achievement"],
    ),
    "marts/campaign/channel_spend": (["mart_shared.campaign_spend_allocated"], ["mart_campaign.channel_spend"]),
    "marts/campaign/spend_summary": (["mart_shared.spend_reconciliation"], ["mart_campaign.spend_summary"]),
    "marts/customer/rfm": (["unified/orders"], ["mart_customer.rfm"]),
}
BOTH = {"campaign_id": "campaign_id", "date": "date"}
CAMPAIGN = {"campaign_id": "campaign_id"}
SCOPED = ["full", "scope"]
MANIFESTS = {
    "unified/campaign_spend": ("manifest.yml", ["campaign_id", "date"], SCOPED, BOTH),
    "unified/daily_spend": ("manifest_daily.yml", ["date"], SCOPED, {"date": "date"}),
    "mart_shared.campaign_spend_allocated": ("mart.yml", ["campaign_id", "date"], SCOPED, BOTH),
    "mart_shared.spend_reconciliation": ("mart_reconciliation.yml", ["date"], SCOPED, {"date": "date"}),
    "mart_finance.budget_daily": ("mart.yml", ["campaign_id", "date"], SCOPED, BOTH),
    "mart_finance.contribution": ("mart.yml", ["campaign_id"], SCOPED, CAMPAIGN),
    "mart_campaign.target_achievement": ("mart.yml", ["campaign_id"], SCOPED, CAMPAIGN),
    "mart_campaign.channel_spend": ("mart.yml", ["channel"], SCOPED, {}),
    "mart_campaign.spend_summary": ("mart.yml", ["date"], ["full"], {}),
    "mart_customer.rfm": ("mart.yml", ["customer_id"], ["full"], {}),
}
EVENT = {
    "event_id": "e1",
    "emitted_at": "2026-10-20T09:00:00+00:00",
    "source": "raw/spend/campaign_spend",
    "keys": {"campaign_id": "CMP19_03", "date": "2019-05-20"},
    "source_version": 5,
}
X = ["CMP19_03"]
D = ["2019-05-20"]


@pytest.fixture
def lineage(monkeypatch, tmp_path):
    entries = []
    for job_id, (inputs, outputs) in JOBS.items():
        job = tmp_path / "jobs" / job_id / "job.py"
        job.parent.mkdir(parents=True, exist_ok=True)
        job.write_text(f"INPUTS = {inputs!r}\nOUTPUTS = {outputs!r}\n")
        for dataset_id in outputs:
            entry = {"dataset_id": dataset_id, "om_fqn": dataset_id, "openlineage": {}, "job_id": job_id, "tags": []}
            entries.append(entry | ({"natural_key": ["id"]} if dataset_id.startswith("raw/") else {}))
    writers = {d: job_id for job_id, (_, outputs) in JOBS.items() for d in outputs}
    for dataset_id, (name, grain, modes, scope_map) in MANIFESTS.items():
        manifest = {"table": dataset_id, "grain": grain, "modes": modes, "scope_map": scope_map, "metrics": []}
        (tmp_path / "jobs" / writers[dataset_id] / name).write_text(yaml.safe_dump(manifest))
    (tmp_path / "datasets").mkdir()
    (tmp_path / "datasets" / "a.yml").write_text(yaml.safe_dump({"datasets": entries}))
    monkeypatch.setenv("FABRIC_CONTRACTS_DIR", str(tmp_path))
    monkeypatch.setenv("FABRIC_JOBS_DIR", str(tmp_path / "jobs"))
    monkeypatch.setenv("FABRIC_CONTROL_MODE", "offline")
    return tmp_path


def by_dataset(affected):
    return {item["dataset_id"]: item["scope"] for item in affected}


def test_order_is_source_then_unified_then_shared_then_slice_marts(lineage):
    order = [item["dataset_id"] for item in fc.affected_by(EVENT)]
    assert order == [
        "raw/spend/campaign_spend",
        "unified/campaign_spend",
        "unified/daily_spend",
        "mart_shared.campaign_spend_allocated",
        "mart_shared.spend_reconciliation",
        "mart_campaign.channel_spend",
        "mart_campaign.spend_summary",
        "mart_campaign.target_achievement",
        "mart_finance.budget_daily",
        "mart_finance.contribution",
    ]


def test_scope_is_projected_onto_each_grain(lineage):
    scopes = by_dataset(fc.affected_by(EVENT))
    assert scopes["raw/spend/campaign_spend"] == {"mode": "full"}
    assert scopes["mart_shared.campaign_spend_allocated"] == {"mode": "scope", "keys": {"campaign_id": X, "date": D}}
    assert scopes["mart_shared.spend_reconciliation"] == {"mode": "scope", "keys": {"date": D}}
    assert scopes["mart_finance.budget_daily"] == {"mode": "scope", "keys": {"campaign_id": X, "date": D}}
    assert scopes["mart_finance.contribution"] == {"mode": "scope", "keys": {"campaign_id": X}}
    assert scopes["mart_campaign.target_achievement"] == {"mode": "scope", "keys": {"campaign_id": X}}


def test_keys_missing_from_scope_map_do_not_narrow(lineage):
    scopes = by_dataset(fc.affected_by(EVENT))
    assert scopes["mart_campaign.channel_spend"] == {"mode": "full"}
    assert scopes["mart_campaign.spend_summary"] == {"mode": "full"}


def test_datasets_not_downstream_of_spend_are_excluded(lineage):
    affected = by_dataset(fc.affected_by(EVENT))
    assert not {"mart_customer.rfm", "unified/orders", "unified/campaigns", "raw/spend/daily_spend"} & set(affected)


def test_plan_runs_each_job_once_with_merged_scope(lineage):
    plan = fc.refresh_plan(fc.affected_by(EVENT))
    jobs = [step["job_id"] for step in plan]
    assert jobs[:3] == ["ingest/spend", "unified/campaign_spend", "marts/shared/campaign_spend"]
    assert len(jobs) == len(set(jobs))
    steps = {step["job_id"]: step for step in plan}
    assert steps["marts/shared/campaign_spend"]["scope"] == {"mode": "scope", "keys": {"campaign_id": X, "date": D}}
    assert steps["ingest/spend"]["needs"] == []
    assert steps["marts/finance/budget_daily"]["needs"] == [
        "ingest/spend",
        "unified/campaign_spend",
        "marts/shared/campaign_spend",
    ]
    assert "marts/finance/budget_daily" not in steps["marts/finance/contribution"]["needs"]


def test_unknown_source_is_rejected(lineage):
    with pytest.raises(KeyError):
        fc.affected_by({**EVENT, "source": "raw/spend/unknown"})


def test_manifest_scope_map_must_target_grain(tmp_path):
    (tmp_path / "mart.yml").write_text(yaml.safe_dump({"table": "t", "grain": ["a"], "scope_map": {"k": "b"}}))
    with pytest.raises(ManifestError, match="not grain columns"):
        load_manifests(tmp_path)


def test_repo_spend_event_reaches_only_spend_descendants():
    order = [item["dataset_id"] for item in fc.affected_by(EVENT)]
    assert order[0] == "raw/spend/campaign_spend"
    assert set(order[1:]) == {
        "unified/campaign_spend",
        "unified/daily_spend",
        "mart_shared.campaign_spend_allocated",
        "mart_shared.spend_reconciliation",
        "mart_finance.budget_daily",
        "mart_finance.contribution",
        "mart_finance.contribution_sku",
        "mart_campaign.target_achievement",
    }
    assert order.index("mart_shared.campaign_spend_allocated") < order.index("mart_finance.budget_daily")
