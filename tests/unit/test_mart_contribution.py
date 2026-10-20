from datetime import date
from decimal import Decimal

import pytest
import yaml

from fabric_control.contracts import columns, load_schema
from tests.unit.test_mart_contracts import METADATA, ROOT, migration_columns

MART_DIR = ROOT / "pipelines" / "jobs" / "marts" / "finance" / "contribution"
MARTS = {
    "mart_finance.contribution": ("mart.yml", "305_p4_contribution"),
    "mart_finance.contribution_sku": ("mart_sku.yml", "306_p4_contribution_sku"),
}


@pytest.mark.parametrize("dataset_id", MARTS)
def test_contract_manifest_and_migration_agree(dataset_id):
    manifest, migration_id = MARTS[dataset_id]
    contract = load_schema(dataset_id)
    names = [name for name, _ in columns(contract)]
    assert names[-3:] == METADATA
    data = yaml.safe_load((MART_DIR / manifest).read_text())
    assert (data["table"], data["grain"], data["modes"]) == (dataset_id, contract["grain"], ["full", "scope"])
    assert data["scope_map"] == {"campaign_id": "campaign_id"}
    sql = (ROOT / "migrations" / "mart_finance" / f"{migration_id}.sql").read_text()
    assert migration_columns(sql) == names


import fabric_control as fc  # noqa: E402
from pipelines import io  # noqa: E402
from pipelines.jobs.marts.finance.contribution import job, transforms  # noqa: E402

JAN, DEC = date(2019, 1, 20), date(2019, 12, 31)


def frames(spark, costs=(("SKU1", "2.00"),)):
    lines = spark.createDataFrame(
        [
            ("o1", "SKU1", "Pen", 3, Decimal("30.00"), JAN, "original"),
            ("o1", "SKU2", "Cap", 1, Decimal("20.00"), JAN, "original"),
            ("o2", "SKU1", "Pen", 1, Decimal("10.00"), DEC, "original"),
            ("o3", "SKU1", "Pen", 5, Decimal("50.00"), JAN, "original"),
        ],
        "order_key STRING, product_sku STRING, product_description STRING, quantity INT, "
        "line_gross_value DECIMAL(18,2), transaction_date_iso DATE, provenance STRING",
    )
    attribution = spark.createDataFrame(
        [("o1", "CMP19_01", "synthetic"), ("o2", "CMP19_01", "synthetic")],
        "order_key STRING, campaign_id STRING, provenance STRING",
    )
    product_cost = spark.createDataFrame(
        [(s, Decimal(c), date(2019, 1, 1), date(2019, 6, 30), "synthetic") for s, c in costs],
        "product_sku STRING, estimated_unit_cost DECIMAL(18,2), valid_from DATE, valid_through DATE, provenance STRING",
    )
    campaigns = spark.createDataFrame(
        [("CMP19_01", "Spring", "synthetic"), ("CMP19_02", "Summer", "synthetic")],
        "campaign_id STRING, campaign_name STRING, provenance STRING",
    )
    spend = spark.createDataFrame(
        [("CMP19_01", JAN, Decimal("7.00"), "synthetic")],
        "campaign_id STRING, date DATE, allocated DECIMAL(18,2), provenance STRING",
    )
    daily = spark.createDataFrame(
        [("CMP19_01", JAN, Decimal("50.00"), "synthetic"), ("CMP19_01", DEC, Decimal("10.00"), "synthetic")],
        "campaign_id STRING, date DATE, attributed_gross_value DECIMAL(18,2), provenance STRING",
    )
    return lines, attribution, product_cost, campaigns, spend, daily


def test_sku_detail_marks_missing_and_out_of_validity_cost(spark):
    lines, attribution, product_cost, *_ = frames(spark)
    rows = {r.product_sku: r for r in transforms.contribution_sku(lines, attribution, product_cost).collect()}
    assert set(rows) == {"SKU1", "SKU2"}
    # SKU1 sold in January (cost valid) and December (outside validity) -> not fully costed.
    assert (rows["SKU1"].quantity, rows["SKU1"].cost_available, rows["SKU1"].reference_cogs) == (4, False, None)
    assert (rows["SKU2"].cost_available, rows["SKU2"].reference_cogs) == (False, None)


def test_contribution_is_gross_minus_cogs_minus_cost(spark):
    lines, attribution, product_cost, campaigns, spend, daily = frames(
        spark, costs=(("SKU1", "2.00"), ("SKU2", "4.00"))
    )
    lines = lines.filter("transaction_date_iso < '2019-07-01'")
    daily = daily.filter("date < '2019-07-01'")
    skus = transforms.contribution_sku(lines, attribution, product_cost)
    out = {r.campaign_id: r for r in transforms.contribution(skus, campaigns, spend, daily).collect()}
    spring = out["CMP19_01"]
    assert (spring.attributed_gross_value, spring.reference_cogs, spring.campaign_cost) == (
        Decimal("50.00"),
        Decimal("10.00"),
        Decimal("7.00"),
    )
    assert (spring.estimated_contribution, spring.skus_without_cost) == (Decimal("33.00"), 0)
    assert (out["CMP19_02"].estimated_contribution, out["CMP19_02"].provenance) == (Decimal("0.00"), "synthetic")
    assert transforms.gross_mismatch(skus, daily).isEmpty()


def lake(monkeypatch, spark):
    lines, attribution, product_cost, campaigns, spend, daily = frames(spark)
    tables = dict(zip(job.INPUTS, (lines, attribution, product_cost, campaigns, spend, daily), strict=True))
    skus = transforms.contribution_sku(lines, attribution, product_cost)
    tables["mart_finance.contribution_sku"] = skus
    tables["mart_finance.contribution"] = transforms.contribution(skus, campaigns, spend, daily)
    calls = {"full": [], "upsert": []}
    monkeypatch.setattr(io, "read_delta", lambda d, version=None: tables[d])
    monkeypatch.setattr(io, "read_pg", lambda t: tables[t])
    monkeypatch.setattr(io, "source_versions", lambda ids: {})
    monkeypatch.setattr(io, "write_pg_full", lambda t, df, run_id, v: calls["full"].append((t, df.count())))
    monkeypatch.setattr(
        io, "upsert_pg", lambda t, df, scope, run_id, versions: calls["upsert"].append((t, df.count())) or (1, 2)
    )
    monkeypatch.setattr(fc.Run, "record_change", lambda self, *args: None)
    monkeypatch.setattr(fc, "emit_lineage", lambda *args: None)
    return calls


def test_job_full_writes_both_marts(monkeypatch, spark):
    calls = lake(monkeypatch, spark)
    job.main({"mode": "full"})
    assert calls["full"] == [("mart_finance.contribution", 2), ("mart_finance.contribution_sku", 2)]


def test_job_scope_upserts_only_the_campaign(monkeypatch, spark):
    calls = lake(monkeypatch, spark)
    job.main({"mode": "scope", "keys": {"campaign_id": ["CMP19_02"]}})
    assert calls["upsert"] == [("mart_finance.contribution", 1), ("mart_finance.contribution_sku", 0)]
