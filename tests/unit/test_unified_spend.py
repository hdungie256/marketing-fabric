from datetime import date
from decimal import Decimal

import pytest

from pipelines.jobs.unified.campaign_spend import transforms
from tests.unit.unified_fixtures import contract, frame, schema

pytest.importorskip("pyspark.sql")

NOTE = "SYNTHETIC"


def allocation(day, amount, campaign_id="CMP19_01"):
    return (day, campaign_id, Decimal(amount), "Online_Spend allocation", "synthetic", NOTE)


def daily(day, online, offline="4500.00"):
    return (day, Decimal(offline), Decimal(online), "original")


def campaigns(spark, campaign_ids=("CMP19_01",)):
    rows = [(c, date(2019, 1, 15), date(2019, 2, 10)) for c in campaign_ids]
    return spark.createDataFrame(rows, "campaign_id STRING, start_date DATE, end_date DATE")


def spend_frames(spark, allocations, days):
    spend = transforms.campaign_spend(frame(spark, "raw/spend/campaign_spend", allocations))
    return spend, transforms.daily_spend(frame(spark, "raw/spend/daily_spend", days))


def test_transforms_match_contracts(spark):
    spend, days = spend_frames(spark, [allocation(date(2019, 1, 15), "797.95")], [daily("1/15/2019", "2000.00")])
    assert schema(spend) == contract("unified/campaign_spend")
    assert schema(days) == contract("unified/daily_spend")


def test_daily_dates_parse_us_format_and_bad_dates_become_null(spark):
    _, days = spend_frames(
        spark, [], [daily("1/5/2019", "1.00"), daily("12/31/2019", "1.00"), daily("2019-13-01", "1")]
    )
    assert [r.date for r in days.collect()] == [date(2019, 1, 5), date(2019, 12, 31), None]


def test_allocated_spend_keeps_synthetic_provenance(spark):
    spend, _ = spend_frames(spark, [allocation(date(2019, 1, 15), "797.95")], [])
    row = spend.collect()[0]
    assert (row.allocated_online_spend, row.provenance, row.provenance_note) == (Decimal("797.95"), "synthetic", NOTE)


def test_cross_checks_find_missing_over_allocated_and_out_of_window_days(spark):
    spend, days = spend_frames(
        spark,
        [
            allocation(date(2019, 1, 15), "100.00"),
            allocation(date(2019, 1, 16), "300.00"),
            allocation(date(2019, 3, 1), "1.00"),
        ],
        [daily("1/15/2019", "100.00"), daily("1/16/2019", "200.00")],
    )
    assert [r.date for r in transforms.days_without_daily_spend(spend, days).collect()] == [date(2019, 3, 1)]
    assert [r.date for r in transforms.days_over_allocated(spend, days).collect()] == [date(2019, 1, 16)]
    assert [r.date for r in transforms.outside_campaign_dates(spend, campaigns(spark)).collect()] == [date(2019, 3, 1)]


import fabric_control as fc  # noqa: E402
from fabric_control.models import GateFailed  # noqa: E402
from pipelines import io  # noqa: E402
from pipelines.jobs.unified.campaign_spend import job  # noqa: E402


def lake(monkeypatch, spark, allocations, days, campaign_ids=("CMP19_01",)):
    tables = {
        "raw/spend/campaign_spend": frame(spark, "raw/spend/campaign_spend", allocations),
        "raw/spend/daily_spend": frame(spark, "raw/spend/daily_spend", days),
        "unified/campaigns": campaigns(spark, campaign_ids),
    }
    written, lineage = {}, []
    monkeypatch.setattr(io, "read_raw", lambda d: tables[d])
    monkeypatch.setattr(io, "read_delta", lambda d, version=None: tables[d])
    monkeypatch.setattr(io, "write_delta", lambda d, df, run_id, replace_where=None: written.update({d: df.collect()}))
    monkeypatch.setattr(fc, "emit_lineage", lambda *args: lineage.append(args))
    return written, lineage


def test_job_writes_both_datasets_and_emits_lineage(monkeypatch, spark):
    written, lineage = lake(monkeypatch, spark, [allocation(date(2019, 1, 15), "50.00")], [daily("1/15/2019", "80")])
    job.main({"mode": "full"})
    assert list(written) == job.OUTPUTS
    assert lineage == [(job.JOB_ID, job.INPUTS, job.OUTPUTS)]


@pytest.mark.parametrize(
    "allocations,campaign_ids,rule",
    [
        ([allocation(date(2019, 1, 15), "50.00", "CMP19_99")], ("CMP19_01",), "campaign_id_in_campaigns"),
        ([allocation(date(2019, 1, 15), "90.00")], ("CMP19_01",), "allocated_not_above_online"),
        ([allocation(date(2019, 1, 20), "1.00")], ("CMP19_01",), "date_in_daily_spend"),
    ],
)
def test_job_gates_before_writing(monkeypatch, spark, allocations, campaign_ids, rule):
    written, _ = lake(monkeypatch, spark, allocations, [daily("1/15/2019", "80")], campaign_ids)
    with pytest.raises(GateFailed, match=rule):
        job.main({"mode": "full"})
    assert written == {}


def test_job_rejects_scoped_refresh(monkeypatch, spark):
    lake(monkeypatch, spark, [], [])
    with pytest.raises(ValueError, match="full refresh only"):
        job.main({"mode": "scope", "keys": {"date": ["2019-01-15"]}})
