"""BR08 e2e: audience saves via app_writer and export stays locked (T-BR08)."""

import json
import os

import psycopg

import fabric_control

DSN = os.environ.get("SERVING_DB_DSN", "")


def test_audience_saves_and_export_stays_locked():
    with psycopg.connect(DSN) as conn, conn.transaction(force_rollback=True):
        conn.execute(
            "INSERT INTO app.segments (audience_id, name, criteria, customer_count, created_by)"
            " VALUES ('e2e-01', 'E2E win-back', %s, 0, 'UG02')",
            (json.dumps({"segment": "All", "category": "Fun", "min_orders": 1}),),
        )
        rows = conn.execute("SELECT customer_count FROM app_v.segments WHERE audience_id = 'e2e-01'").fetchall()
        assert rows == [(0,)]
    allowed, reason = fabric_control.can_export("mart_customer.rfm", "UG02")
    assert allowed is False
    assert reason == "Contact export disabled — no marketing consent data (R12)"
