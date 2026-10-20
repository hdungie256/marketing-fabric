import importlib
import json
import os

import psycopg
from psycopg import sql
from psycopg.rows import dict_row

import fabric_control as fc
from pipelines import io
from pipelines.io.pg import grain
from pipelines.io.scope import restrict

EVENT = {
    "event_id": "e2e-scoped",
    "emitted_at": "2026-10-20T09:00:00+00:00",
    "source": "raw/spend/campaign_spend",
    "keys": {"campaign_id": "CMP19_03", "date": "2019-05-20"},
    "source_version": 0,
}


def query(statement, params=()):
    with psycopg.connect(os.environ["SERVING_DB_DSN"], row_factory=dict_row) as conn:
        return conn.execute(statement, params).fetchall()


def snapshot(table):
    schema, name = table.split(".")
    rows = query(sql.SQL("SELECT * FROM {}").format(sql.Identifier(schema, name)))
    return {tuple(str(r[c]) for c in grain(table)): r for r in rows}


def in_scope(key, table, scope):
    keys = restrict(scope, grain(table)).get("keys", {})
    return all(str(key[grain(table).index(c)]) in map(str, values) for c, values in keys.items())


def run_job(job_id, scope):
    importlib.import_module(f"pipelines.jobs.{job_id.replace('/', '.')}.job").main(scope)


def plan():
    affected = fc.affected_by(EVENT)
    tables = [a["dataset_id"] for a in affected if a["dataset_id"].startswith("mart_")]
    return fc.refresh_plan(affected)[1:], tables


def test_scoped_run_matches_full_and_keeps_other_rows():
    fc.run_migrations()
    steps, tables = plan()
    assert [s["job_id"] for s in steps][:2] == ["unified/campaign_spend", "marts/shared/campaign_spend"]
    for step in steps:
        run_job(step["job_id"], {"mode": "full"})
    before = {t: snapshot(t) for t in tables}
    for step in steps:
        run_job(step["job_id"], step["scope"])
        [run] = query(
            "SELECT scope, delta_version, delta_version_before FROM ops.runs WHERE job_id = %s "
            "ORDER BY started_at DESC LIMIT 1",
            (step["job_id"],),
        )
        assert run["scope"] == step["scope"]
        if step["job_id"].startswith("unified/"):
            assert run["delta_version"] == run["delta_version_before"] + 1
    for table in tables:
        scope = next(s["scope"] for s in steps if s["job_id"] == fc.load_registry()[table]["job_id"])
        after = snapshot(table)
        assert after.keys() == before[table].keys(), table
        touched = 0
        for key, row in after.items():
            old = before[table][key]
            assert {c: v for c, v in row.items() if not c.startswith("_")} == {
                c: v for c, v in old.items() if not c.startswith("_")
            }, (table, key)
            if in_scope(key, table, scope):
                touched += 1
                assert row["_refreshed_at"] > old["_refreshed_at"], (table, key)
            else:
                assert row["_refreshed_at"] == old["_refreshed_at"], (table, key)
        assert touched, table


def test_upsert_returns_before_after_and_logs_metric_changes(monkeypatch):
    table = "mart_finance.budget_daily"
    scope = {"mode": "scope", "keys": {"campaign_id": ["CMP19_03"], "date": ["2019-05-20"]}}
    original = io.narrow(io.read_pg(table), scope).drop("_refreshed_at", "_run_id", "_source_version").cache()
    from pyspark.sql import functions as F

    bumped = original.withColumn("allocated", (F.col("allocated") + 1).cast("decimal(18,2)"))
    monkeypatch.setenv("FABRIC_EVENT_ID", "e2e-upsert")
    try:
        with fc.run("marts/finance/budget_daily", scope) as run:
            before, after = io.upsert_pg(table, bumped, scope, run.run_id, {})
            assert run.record_change(table, before, after) == 1
        [change] = query("SELECT * FROM ops.metric_change_log WHERE run_id = %s", (run.run_id,))
        assert change["event_id"] == "e2e-upsert" and change["dataset_id"] == table
        assert change["grain_key"] == {"campaign_id": "CMP19_03", "date": "2019-05-20"}
        assert change["new_value"] - change["old_value"] == 1
        assert json.loads(json.dumps(change["grain_key"])) == change["grain_key"]
    finally:
        run_job("marts/finance/budget_daily", scope)
    [row] = io.narrow(io.read_pg(table), scope).select("allocated").collect()
    assert row.allocated == original.first().allocated
