import json
import os
import urllib.request
from collections import Counter
from decimal import Decimal

import psycopg
from psycopg.rows import dict_row

from fabric_control import affected_by
from fabric_control.clients import airflow
from fabric_control.manifests import load_manifests
from fabric_control.policy import load_policy
from fabric_control.registry import load_registry

CAMPAIGN, DAY = "CMP19_05", "2019-11-12"
URL = f"{os.environ.get('API_URL', '')}/spend/campaign_spend/{CAMPAIGN}/{DAY}"
ORIGINAL, EDITED = Decimal("1356.33"), Decimal("1156.33")
TARGET_SECONDS = 120
# Spec "Change-log rows" table; term_id is skipped on purpose (term_for mislabels budget_daily.allocated).
EXPECTED_LOG = Counter(
    [
        ("mart_shared.campaign_spend_allocated", Decimal("1356.33"), Decimal("1156.33")),
        ("mart_finance.budget_daily", Decimal("1356.33"), Decimal("1156.33")),
        ("mart_shared.spend_reconciliation", Decimal("1356.33"), Decimal("1156.33")),
        ("mart_shared.spend_reconciliation", Decimal("2034.49"), Decimal("2234.49")),
        ("mart_campaign.target_achievement", Decimal("24593.53"), Decimal("24393.53")),
        ("mart_finance.contribution", Decimal("24593.53"), Decimal("24393.53")),
    ]
)


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
    return result["event"]


def metric_marts():
    registry = load_registry()
    return {
        table: manifest["grain"]
        for table, manifest in load_manifests().items()
        if table.startswith("mart_") and table in registry and manifest.get("metrics")
    }


def snapshot(marts):
    rows = {}
    for table, grain in marts.items():
        columns = ", ".join(grain)
        for r in query(f"SELECT {columns}, _refreshed_at FROM {table}"):
            rows[(table, tuple(str(r[c]) for c in grain))] = r["_refreshed_at"]
    return rows


def test_spend_edit_refreshes_only_scope_and_logs_changes():
    marts = metric_marts()
    [current] = query(
        "SELECT allocated FROM mart_finance.budget_daily WHERE campaign_id = %s AND date = %s", (CAMPAIGN, DAY)
    )
    assert current["allocated"] == ORIGINAL
    before = snapshot(marts)
    try:
        event = edit(EDITED)
        [latency] = query(
            "SELECT extract(epoch FROM max(r.ended_at) - e.emitted_at) AS s FROM ops.runs r "
            "JOIN ops.source_events e USING (event_id) WHERE event_id = %s GROUP BY e.emitted_at",
            (event["event_id"],),
        )
        assert latency["s"] < TARGET_SECONDS

        after = snapshot(marts)
        moved = {key for key, at in after.items() if before.get(key) != at}
        assert moved
        scopes = {a["dataset_id"]: a["scope"] for a in affected_by(event)}
        assert {table for table, _ in moved} <= set(scopes)
        for table, values in moved:
            scope = scopes[table]
            if scope["mode"] != "scope":
                continue
            row = dict(zip(marts[table], values, strict=True))
            for column, allowed in scope["keys"].items():
                assert row[column] in {str(v) for v in allowed}, (table, row)

        # Read as UG04 through the policy view; no app import, so the test runs in the fabric-jobs image.
        with psycopg.connect(os.environ["SERVING_DB_DSN"]) as conn, conn.transaction(force_rollback=True):
            conn.execute(f"SET LOCAL ROLE {load_policy().roles['UG04']}")
            logged = conn.execute(
                "SELECT dataset_id, old_value, new_value FROM ops_v.metric_change_log WHERE event_id = %s",
                (event["event_id"],),
            ).fetchall()
        assert Counter(logged) == EXPECTED_LOG, logged
    finally:
        edit(ORIGINAL)
