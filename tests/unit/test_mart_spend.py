from datetime import date
from decimal import Decimal

import pytest
import yaml

from fabric_control.contracts import columns, load_schema
from tests.unit.test_mart_contracts import METADATA, MIGRATIONS, ROOT, migration_columns

MART_DIR = ROOT / "pipelines" / "jobs" / "marts" / "shared" / "campaign_spend"
MARTS = {
    "mart_shared.campaign_spend_allocated": ("mart.yml", "302_p4_campaign_spend_allocated"),
    "mart_shared.spend_reconciliation": ("mart_reconciliation.yml", "303_p4_spend_reconciliation"),
}


@pytest.mark.parametrize("dataset_id", MARTS)
def test_contract_manifest_and_migration_agree(dataset_id):
    manifest, migration_id = MARTS[dataset_id]
    contract = load_schema(dataset_id)
    names = [name for name, _ in columns(contract)]
    assert names[-3:] == METADATA and "provenance" in names
    data = yaml.safe_load((MART_DIR / manifest).read_text())
    assert (data["table"], data["grain"], data["modes"]) == (dataset_id, contract["grain"], ["full"])
    assert set(data["metrics"]) <= set(names)
    sql = (MIGRATIONS / f"{migration_id}.sql").read_text()
    assert sql.startswith("-- depends: 000_create_schemas")
    assert [n for n in migration_columns(sql) if n.upper() != "CHECK"] == names
    assert f"PRIMARY KEY ({', '.join(contract['grain'])})" in sql
    assert (MIGRATIONS / f"{migration_id}.rollback.sql").read_text().strip() == f"DROP TABLE {dataset_id};"


def test_shared_metrics_match_contracts():
    entries = {
        e["dataset_id"]: e
        for e in yaml.safe_load((ROOT / "contracts" / "shared_metrics.yml").read_text())["shared_metrics"]
    }
    for dataset_id in MARTS:
        assert entries[dataset_id]["grain"] == load_schema(dataset_id)["grain"], dataset_id


pytest.importorskip("pyspark.sql")

from pipelines.jobs.marts.shared.campaign_spend import transforms  # noqa: E402
from tests.unit.unified_fixtures import contract, frame, schema  # noqa: E402

D1, D2, D3 = date(2019, 1, 15), date(2019, 1, 16), date(2019, 1, 17)


def spend(spark, rows):
    return frame(
        spark,
        "unified/campaign_spend",
        [(c, d, Decimal(a), "Online_Spend allocation", "synthetic", "SYNTHETIC") for c, d, a in rows],
    )


def daily(spark, rows):
    return frame(spark, "unified/daily_spend", [(d, Decimal(on), Decimal("4500.00"), "original") for d, on in rows])


def test_allocated_matches_contract(spark):
    out = transforms.allocated(spend(spark, [("CMP19_01", D1, "10.00")]))
    assert schema(out) == contract("mart_shared.campaign_spend_allocated")[:-3]


def test_reconciliation_splits_every_day_without_double_counting(spark):
    allocations = spend(spark, [("CMP19_01", D1, "30.00"), ("CMP19_02", D1, "20.00"), ("CMP19_01", D2, "5.00")])
    days = daily(spark, [(D1, "100.00"), (D2, "5.00"), (D3, "70.00")])
    recon = transforms.reconciliation(days, allocations)
    assert schema(recon) == contract("mart_shared.spend_reconciliation")[:-3]
    rows = {r.date: (r.allocated, r.unallocated, r.provenance) for r in recon.collect()}
    assert rows == {
        D1: (Decimal("50.00"), Decimal("50.00"), "synthetic"),
        D2: (Decimal("5.00"), Decimal("0.00"), "synthetic"),
        D3: (Decimal("0.00"), Decimal("70.00"), "original"),
    }
    assert transforms.unbalanced_days(recon).isEmpty()
    assert transforms.total(recon, "allocated") + transforms.total(recon, "unallocated") == Decimal("175.00")


import fabric_control as fc  # noqa: E402
from fabric_control.models import GateFailed  # noqa: E402
from pipelines import io  # noqa: E402
from pipelines.jobs.marts.shared.campaign_spend import job  # noqa: E402

VERSIONS = {"raw/spend/campaign_spend": 1, "raw/spend/daily_spend": 1}


def lake(monkeypatch, spark, allocations, days):
    tables = {"unified/campaign_spend": spend(spark, allocations), "unified/daily_spend": daily(spark, days)}
    written, lineage = {}, []
    monkeypatch.setattr(io, "read_delta", lambda d, version=None: tables[d])
    monkeypatch.setattr(io, "source_versions", lambda ids: VERSIONS)
    monkeypatch.setattr(io, "write_pg_full", lambda t, df, run_id, versions: written.update({t: df.collect()}))
    monkeypatch.setattr(fc, "emit_lineage", lambda *args: lineage.append(args))
    return written, lineage


def test_job_writes_both_marts(monkeypatch, spark):
    written, lineage = lake(monkeypatch, spark, [("CMP19_01", D1, "30.00")], [(D1, "100.00"), (D2, "8.00")])
    job.main({"mode": "full"})
    assert list(written) == job.OUTPUTS
    assert [r.unallocated for r in written["mart_shared.spend_reconciliation"]] == [Decimal("70.00"), Decimal("8.00")]
    assert lineage == [(job.JOB_ID, job.INPUTS, job.OUTPUTS)]


def test_job_gates_allocation_on_day_without_daily_spend(monkeypatch, spark):
    written, _ = lake(monkeypatch, spark, [("CMP19_01", D3, "30.00")], [(D1, "100.00")])
    with pytest.raises(GateFailed, match="allocated_total_matches_reconciliation"):
        job.main({"mode": "full"})
    assert written == {}


def test_job_rejects_scoped_refresh(monkeypatch, spark):
    lake(monkeypatch, spark, [], [])
    with pytest.raises(ValueError, match="full refresh only"):
        job.main({"mode": "scope", "keys": {"date": ["2019-01-15"]}})
