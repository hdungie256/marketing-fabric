import json
import os
import urllib.request

import psycopg
from psycopg.rows import dict_row

from fabric_control.clients import airflow

URL = f"{os.environ['API_URL']}/spend/campaign_spend/CMP19_03/2019-05-20"
TARGET_SECONDS = 120


def query(statement, params=()):
    with psycopg.connect(os.environ["SERVING_DB_DSN"], row_factory=dict_row) as conn:
        return conn.execute(statement, params).fetchall()


def edit(value):
    body = json.dumps({"allocated_online_spend": str(value)}).encode()
    headers = {"Content-Type": "application/json", "X-Fabric-Role": "UG04"}
    request = urllib.request.Request(URL, body, headers, method="PUT")
    with urllib.request.urlopen(request, timeout=30) as response:
        result = json.loads(response.read())
    assert airflow.wait("partial_refresh", result["dag_run_id"], timeout=300) == "success"
    return result["event"]["event_id"]


def refreshed():
    return {
        (r["campaign_id"], r["_refreshed_at"])
        for r in query("SELECT campaign_id, _refreshed_at FROM mart_finance.contribution")
    }


def test_spend_edit_refreshes_only_its_campaign_within_two_minutes():
    [original] = query(
        "SELECT allocated FROM mart_finance.budget_daily WHERE campaign_id = 'CMP19_03' AND date = '2019-05-20'"
    )
    before = refreshed()
    event_id = edit(original["allocated"] + 1)
    try:
        runs = query("SELECT job_id, status FROM ops.runs WHERE event_id = %s ORDER BY started_at", (event_id,))
        assert [r["job_id"] for r in runs][:3] == [
            "ingest/spend",
            "unified/campaign_spend",
            "marts/shared/campaign_spend",
        ]
        assert {r["status"] for r in runs} == {"success"}
        [latency] = query(
            "SELECT extract(epoch FROM max(r.ended_at) - e.emitted_at) AS s FROM ops.runs r "
            "JOIN ops.source_events e USING (event_id) WHERE event_id = %s GROUP BY e.emitted_at",
            (event_id,),
        )
        assert latency["s"] < TARGET_SECONDS
        changed = {campaign for campaign, _ in refreshed() - before}
        assert changed == {"CMP19_03"}
        logged = query("SELECT term_id FROM ops.metric_change_log WHERE event_id = %s", (event_id,))
        assert logged
    finally:
        edit(original["allocated"])
