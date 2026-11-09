import os
from typing import Any

COLUMNS = (
    "load_id",
    "dataset_id",
    "source_rows",
    "raw_rows",
    "baseline_rows",
    "source_checksum",
    "raw_checksum",
    "passed",
    "reason",
)
# Raw dataset -> highest _source_version among its passed loads, for io.source_versions(). Kept for the process, so
# the marts of one platform/full_refresh or platform/partial_refresh read each raw table once. Only
# write_reconciliation() changes which loads passed, and it drops that dataset's entry. ponytail: a reconciliation
# written by another process is not seen; the one-slot fabric_writes pool keeps writers to one at a time.
PASSED_VERSIONS: dict[str, int] = {}


def connect():
    import psycopg

    return psycopg.connect(os.environ["SERVING_DB_DSN"], autocommit=True)


def write_reconciliation(check: dict[str, Any], run_id: str) -> None:
    PASSED_VERSIONS.pop(check["dataset_id"], None)
    values = [check[c] for c in COLUMNS]
    updates = ", ".join(f"{c} = EXCLUDED.{c}" for c in (*COLUMNS[2:], "run_id"))
    with connect() as conn:
        conn.execute(
            f"""
            INSERT INTO ops.load_reconciliation ({", ".join(COLUMNS)}, run_id)
            VALUES ({", ".join(["%s"] * (len(COLUMNS) + 1))})
            ON CONFLICT (load_id, dataset_id) DO UPDATE SET {updates}, checked_at = now()
            """,
            (*values, run_id),
        )


def passed_loads(dataset_id: str) -> list[str]:
    with connect() as conn:
        rows = conn.execute(
            "SELECT load_id FROM ops.load_reconciliation WHERE dataset_id = %s AND passed",
            (dataset_id,),
        ).fetchall()
    return [r[0] for r in rows]
