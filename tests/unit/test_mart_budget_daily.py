from datetime import date
from decimal import Decimal

import pytest
import yaml

from fabric_control.contracts import columns, load_schema
from tests.unit.test_mart_contracts import METADATA, ROOT, migration_columns

DATASET = "mart_finance.budget_daily"
MART_DIR = ROOT / "pipelines" / "jobs" / "marts" / "finance" / "budget_daily"
MIGRATION = ROOT / "migrations" / "mart_finance" / "304_p4_budget_daily"


def test_contract_manifest_and_migration_agree():
    contract = load_schema(DATASET)
    names = [name for name, _ in columns(contract)]
    assert names[-3:] == METADATA
    manifest = yaml.safe_load((MART_DIR / "mart.yml").read_text())
    assert manifest["grain"] == contract["grain"] == ["campaign_id", "date"]
    assert manifest["modes"] == ["full", "scope"]
    assert set(manifest["scope_map"]) == {"campaign_id", "date"}
    assert set(manifest["metrics"]) <= set(names)
    sql = MIGRATION.with_suffix(".sql").read_text()
    assert migration_columns(sql) == names and "PRIMARY KEY (campaign_id, date)" in sql
    assert MIGRATION.with_suffix(".rollback.sql").read_text().strip() == f"DROP TABLE {DATASET};"


import fabric_control as fc  # noqa: E402
from fabric_control.models import GateFailed  # noqa: E402
from pipelines import io  # noqa: E402
from pipelines.jobs.marts.finance.budget_daily import job, transforms  # noqa: E402

D1, D2 = date(2019, 1, 15), date(2019, 1, 16)


def frames(spark, spend_rows, order_rows, campaign_ids=("CMP19_01", "CMP19_02")):
    spend = spark.createDataFrame(
        [(c, d, Decimal(a), "synthetic") for c, d, a in spend_rows],
        "campaign_id STRING, date DATE, allocated DECIMAL(18,2), provenance STRING",
    )
    attributed = spark.createDataFrame(
        [(c, d, n, Decimal(v), "original") for c, d, n, v in order_rows],
        "campaign_id STRING, date DATE, attributed_orders INT, attributed_gross_value DECIMAL(18,2), provenance STRING",
    )
    campaigns = spark.createDataFrame(
        [(c, f"Name {c}", "Paid Search", Decimal("1000.00")) for c in campaign_ids],
        "campaign_id STRING, campaign_name STRING, channel STRING, budget DECIMAL(18,2)",
    )
    return spend, attributed, campaigns


def test_budget_daily_joins_spend_and_orders_per_campaign_day(spark):
    spend, attributed, campaigns = frames(
        spark,
        [("CMP19_01", D1, "10.00"), ("CMP19_01", D2, "5.00")],
        [("CMP19_01", D1, 2, "40.00"), ("CMP19_02", D2, 1, "9.00")],
    )
    out = transforms.budget_daily(spend, attributed, campaigns)
    names = [n for n, _ in columns(load_schema(DATASET))][:-3]
    assert out.columns == names
    rows = {(r.campaign_id, r.date): r for r in out.collect()}
    assert (rows["CMP19_01", D1].allocated, rows["CMP19_01", D1].attributed_orders) == (Decimal("10.00"), 2)
    assert (rows["CMP19_01", D2].attributed_orders, rows["CMP19_01", D2].provenance) == (0, "synthetic")
    assert (rows["CMP19_02", D2].allocated, rows["CMP19_02", D2].provenance) == (Decimal("0.00"), "original")
    assert {r.campaign_budget for r in rows.values()} == {Decimal("1000.00")}


def test_in_scope_narrows_only_by_keys_the_frame_has(spark):
    spend, _, campaigns = frames(spark, [("CMP19_01", D1, "1.00"), ("CMP19_01", D2, "1.00")], [])
    scope = {"mode": "scope", "keys": {"campaign_id": ["CMP19_01"], "date": [D1]}}
    assert transforms.in_scope(spend, scope).count() == 1
    assert [r.campaign_id for r in transforms.in_scope(campaigns, scope).collect()] == ["CMP19_01"]
    assert transforms.in_scope(spend, {"mode": "full"}).count() == 2


def lake(monkeypatch, spark, spend_rows, order_rows, campaign_ids=("CMP19_01", "CMP19_02")):
    spend, attributed, campaigns = frames(spark, spend_rows, order_rows, campaign_ids)
    tables = {job.INPUTS[0]: spend, job.INPUTS[1]: attributed, job.INPUTS[2]: campaigns}
    tables[DATASET] = transforms.budget_daily(spend, attributed, campaigns)  # the previous full run
    calls = {"full": [], "upsert": [], "change": []}
    monkeypatch.setattr(io, "read_pg", lambda t: tables[t])
    monkeypatch.setattr(io, "read_delta", lambda d, version=None: tables[d])
    monkeypatch.setattr(io, "source_versions", lambda ids: {"raw/spend/campaign_spend": 1})
    monkeypatch.setattr(io, "write_pg_full", lambda t, df, run_id, v: calls["full"].append((t, df.count())))
    monkeypatch.setattr(
        io,
        "upsert_pg",
        lambda t, df, scope, run_id, versions: calls["upsert"].append((t, df.count(), scope)) or ("b", "a"),
    )
    monkeypatch.setattr(
        fc.Run, "record_change", lambda self, d, before, after: calls["change"].append((d, before, after))
    )
    monkeypatch.setattr(fc, "emit_lineage", lambda *args: None)
    return calls


def test_full_refresh_writes_whole_mart(monkeypatch, spark):
    calls = lake(monkeypatch, spark, [("CMP19_01", D1, "10.00")], [("CMP19_02", D2, 1, "9.00")])
    job.main({"mode": "full"})
    assert calls["full"] == [(DATASET, 2)] and calls["upsert"] == []


def test_scoped_refresh_upserts_scope_rows_and_records_change(monkeypatch, spark):
    calls = lake(monkeypatch, spark, [("CMP19_01", D1, "10.00"), ("CMP19_02", D1, "3.00")], [])
    scope = {"mode": "scope", "keys": {"campaign_id": ["CMP19_01"]}}
    job.main(scope)
    assert calls["upsert"] == [(DATASET, 1, scope)]
    assert calls["change"] == [(DATASET, "b", "a")] and calls["full"] == []


def test_unknown_campaign_gates_before_write(monkeypatch, spark):
    calls = lake(monkeypatch, spark, [("CMP19_99", D1, "10.00")], [], campaign_ids=("CMP19_01",))
    with pytest.raises(GateFailed, match="campaign_id_in_campaigns"):
        job.main({"mode": "full"})
    assert calls["full"] == []
