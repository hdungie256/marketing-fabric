"""Run the warehouse baseline: full batch x3, then the BR16 spend edit x3, with reconciliation checks (Story 9.3).

Usage: python benchmark/warehouse/run.py → benchmark/results/warehouse.csv
"""

from __future__ import annotations

import csv
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from benchmark.measure import ROOT, run  # noqa: E402

RESULTS = ROOT / "benchmark" / "results"
IMAGE = "postgres:16.4-alpine"
DSN = "postgresql://postgres:bench@bench-warehouse:5432/warehouse_baseline"
JOBS = "marketing-fabric/fabric-jobs:latest"
EDIT = ("CMP19_05", "2019-11-12", "1156.33")  # the BR16 e2e edit (tests/e2e/test_br16.py)
CHECKS = {  # name: (SQL, expected before edit, expected after edit)
    "attributed_orders_total": ("SELECT SUM(attributed_orders) FROM wh.br01_campaign_overview", "1290", "1290"),
    "online_spend_total": ("SELECT SUM(online_spend) FROM wh.br10_spend_daily", "695646.47", "695646.47"),
    "allocated_total": ("SELECT SUM(allocated) FROM wh.br10_spend_daily", "98569.53", "98369.53"),
    "unallocated_total": ("SELECT SUM(unallocated) FROM wh.br10_spend_daily", "597076.94", "597276.94"),
    "unbalanced_days": (
        "SELECT COUNT(*) FROM wh.br10_spend_daily WHERE allocated + unallocated <> online_spend",
        "0",
        "0",
    ),
    "edited_day_unallocated": (
        "SELECT unallocated FROM wh.br10_spend_daily WHERE spend_date = '2019-11-12'",
        "2034.49",
        "2234.49",
    ),
    "edited_campaign_cost": (
        "SELECT allocated FROM wh.br10_campaign WHERE campaign_id = 'CMP19_05'",
        "24593.53",
        "24393.53",
    ),
}


def psql(sql: str) -> str:
    out = subprocess.run(
        ["docker", "exec", "bench-warehouse", "psql", "-U", "postgres", "-d", "warehouse_baseline", "-tAc", sql],
        capture_output=True,
        text=True,
        check=True,
    )
    return out.stdout.strip()


def start() -> None:
    subprocess.run(["docker", "rm", "-f", "bench-warehouse"], capture_output=True)
    subprocess.run(["docker", "network", "create", "fabric-bench"], capture_output=True)
    subprocess.run(
        [
            "docker",
            "run",
            "-d",
            "--name",
            "bench-warehouse",
            "--network",
            "fabric-bench",
            "--memory=1g",
            "-e",
            "POSTGRES_PASSWORD=bench",
            "-e",
            "POSTGRES_DB=warehouse_baseline",
            IMAGE,
        ],
        check=True,
        capture_output=True,
    )
    while subprocess.run(
        ["docker", "exec", "bench-warehouse", "pg_isready", "-U", "postgres", "-d", "warehouse_baseline"],
        capture_output=True,
    ).returncode:
        time.sleep(0.5)
    time.sleep(2)  # the image restarts once after init; wait for the final server


def main() -> None:
    start()
    rows = []
    for scenario, args in (("full_batch", []), ("br16_spend_edit", ["--spend", *EDIT])):
        for attempt in range(1, 4):
            result = run(
                JOBS,
                ["python", "-m", "benchmark.warehouse.etl", *args],
                ROOT / "benchmark" / "data",
                extra=["--network", "fabric-bench", "-e", f"WAREHOUSE_DSN={DSN}"],
            )
            column = 1 if scenario == "full_batch" else 2
            checks = {name: psql(spec[0]) == spec[column] for name, spec in CHECKS.items()}
            row = {
                "scenario": scenario,
                "run": attempt,
                "wall_s": result["wall_s"],
                "batch_s": result["job_s"],
                "load_s": result["load_s"],
                "transform_s": result["transform_s"],
                "checks_passed": sum(checks.values()),
                "checks_total": len(checks),
                "failed_checks": ";".join(k for k, ok in checks.items() if not ok),
            }
            print(row, flush=True)
            rows.append(row)
    subprocess.run(["docker", "rm", "-f", "bench-warehouse"], capture_output=True)
    RESULTS.mkdir(exist_ok=True)
    with (RESULTS / "warehouse.csv").open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)


if __name__ == "__main__":
    main()
