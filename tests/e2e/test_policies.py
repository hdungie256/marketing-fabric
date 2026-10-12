import psycopg
import pytest

import fabric_control as fc
from fabric_control.clients import postgres
from fabric_control.policy import GENERATED, PolicyError, load_policy

ORDERS = "mart_shared.campaign_attributed_orders"
ORDER = (
    "INSERT INTO mart_shared.campaign_attributed_orders VALUES "
    "('e2e-policy', 'CMP-01', '2025-01-01', 1000042, 10, true, 'original', now(), 'e2e', '{}')"
)


@pytest.fixture(scope="module")
def synced():
    fc.run_migrations()
    fc.sync_policies()


def as_role(conn, login, query):
    with conn.transaction(force_rollback=True):
        conn.execute(f"SET LOCAL ROLE {login}")
        return conn.execute(query).fetchall()


def test_sync_then_verify_is_idempotent(synced):
    fc.verify_policies()
    fc.sync_policies()
    fc.verify_policies()


def test_one_generated_view_per_serving_table(synced):
    with postgres.connect() as conn:
        tables = postgres.serving_tables(conn)
        views = conn.execute(
            "SELECT schemaname || '.' || viewname, obj_description(c.oid, 'pg_class') FROM pg_views v "
            "JOIN pg_class c ON c.relname = v.viewname AND c.relnamespace = v.schemaname::regnamespace "
            "WHERE schemaname LIKE '%\\_v'"
        ).fetchall()
        for dataset_id, columns in tables.items():
            schema, table = dataset_id.split(".")
            names = [d.name for d in conn.execute(f'SELECT * FROM "{schema}_v"."{table}" LIMIT 0').description]
            assert [n for n in names if not n.endswith("__denied")] == columns
    assert {name for name, _ in views} == {d.replace(".", "_v.", 1) for d in tables}
    assert {comment for _, comment in views} == {GENERATED}


def test_role_reads_view_but_not_table(synced):
    with postgres.connect() as conn:
        assert as_role(conn, "marketing_analyst", "SELECT count(*) FROM mart_shared_v.campaign_attributed_daily")
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            as_role(conn, "marketing_analyst", "SELECT count(*) FROM mart_shared.campaign_attributed_daily")
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            as_role(conn, "marketing_analyst", "SELECT count(*) FROM ops.runs")
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            as_role(conn, "finance_controller", "SELECT count(*) FROM mart_shared_v.campaign_attributed_orders")


def test_identifier_masked_unless_role_needs_it(synced):
    query = "SELECT customer_id FROM mart_shared_v.campaign_attributed_orders WHERE order_key = 'e2e-policy'"
    with postgres.connect() as conn, conn.transaction(force_rollback=True):
        conn.execute(ORDER)
        assert as_role(conn, "marketing_analyst", query) == [("1****42",)]
        assert as_role(conn, "crm_marketing", query) == [("1000042",)]


def test_effective_matrix_matches_policy(synced):
    policy = load_policy()
    matrix = {(r["role"], r["dataset_id"], r["column"]): r["action"] for r in fc.effective_matrix()}
    assert matrix["UG01", ORDERS, "customer_id"] == "mask:partial"
    assert matrix["UG02", ORDERS, "customer_id"] == "allow"
    assert matrix["UG04", ORDERS, "customer_id"] == "deny"
    with postgres.connect() as conn:
        assert len(matrix) == len(policy.effective(postgres.serving_tables(conn)))


def test_writers_write_only_their_schema(synced):
    with postgres.connect() as conn:
        assert as_role(conn, "ops_writer", "SELECT count(*) FROM ops.runs")
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            as_role(conn, "ops_writer", "SELECT count(*) FROM mart_shared.campaign_attributed_daily")
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            as_role(conn, "app_writer", "SELECT count(*) FROM ops.runs")


def test_untagged_column_fails_and_keeps_views(synced):
    with postgres.connect() as conn:
        conn.execute("CREATE TABLE ops.e2e_untagged (secret text)")
        try:
            with pytest.raises(PolicyError, match="ops.e2e_untagged.secret"):
                fc.sync_policies()
        finally:
            conn.execute("DROP TABLE ops.e2e_untagged")
        assert as_role(conn, "data_ops", "SELECT count(*) FROM ops_v.runs")


def test_verify_detects_direct_grant(synced):
    with postgres.connect() as conn:
        conn.execute("GRANT USAGE ON SCHEMA ops TO data_ops")
        conn.execute("GRANT SELECT ON ops.runs TO data_ops")
        try:
            with pytest.raises(PolicyError, match="UG06 can read ops.runs directly"):
                fc.verify_policies()
        finally:
            fc.sync_policies()
    fc.verify_policies()
