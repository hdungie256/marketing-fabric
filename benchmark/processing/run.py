"""Spark vs Flink at ×1, ×10, ×100: 3 runs each, median, then an output equality check per scale (Story 9.1).

Usage (host): python benchmark/processing/run.py [scales...]   → benchmark/results/processing*.csv
Data lives in benchmark/data (git-ignored); build it with data.py inside the fabric-jobs image first.
"""

from __future__ import annotations

import csv
import statistics
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from benchmark.measure import ROOT, run  # noqa: E402

DATA = ROOT / "benchmark" / "data"
RESULTS = ROOT / "benchmark" / "results"
IMAGES = {"spark": "marketing-fabric/fabric-jobs:latest", "flink": "marketing-fabric/flink-bench:2.2.1"}
RUNS = 3
ENGINE_MEMORY = {"spark": "driver 2g", "flink": "minicluster default"}


def job(engine: str, scale: int) -> list[str]:
    return ["python", "-m", f"benchmark.processing.{engine}_job", f"/bench/x{scale}", f"/bench/out/{engine}/x{scale}"]


def main(scales: list[int]) -> None:
    RESULTS.mkdir(exist_ok=True)
    runs = []
    for scale in scales:
        lines = sum(1 for _ in (DATA / f"x{scale}" / "lines.csv").open())
        for engine, image in IMAGES.items():
            for attempt in range(1, RUNS + 1):
                result = run(image, job(engine, scale), DATA) | {"scale": scale, "run": attempt, "lines_in": lines}
                print(result, flush=True)
                runs.append(result)
        check = subprocess.run(
            [
                "docker",
                "run",
                "--rm",
                "-v",
                f"{ROOT}:/srv:ro",
                "-v",
                f"{DATA}:/bench",
                "-w",
                "/srv",
                "-e",
                "PYTHONPATH=/srv",
                IMAGES["spark"],
                "python",
                "-m",
                "benchmark.processing.compare",
                f"/bench/out/spark/x{scale}",
                f"/bench/out/flink/x{scale}",
            ],
            capture_output=True,
            text=True,
        )
        print(check.stdout)
        for result in runs:
            if result["scale"] == scale:
                result["outputs_equal"] = check.returncode == 0
    fields = [
        "engine",
        "scale",
        "run",
        "lines_in",
        "wall_s",
        "job_s",
        "peak_bytes",
        "cpus",
        "mem_limit",
        "outputs_equal",
    ]
    with (RESULTS / "processing_runs.csv").open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        w.writerows(runs)
    with (RESULTS / "processing.csv").open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow(
            [
                "engine",
                "scale",
                "lines_in",
                "median_wall_s",
                "median_job_s",
                "median_peak_mib",
                "cpus",
                "mem_limit",
                "engine_memory",
                "outputs_equal",
            ]
        )
        for scale in scales:
            for engine in IMAGES:
                rs = [r for r in runs if r["engine"] == engine and r["scale"] == scale]
                w.writerow(
                    [
                        engine,
                        scale,
                        rs[0]["lines_in"],
                        statistics.median(r["wall_s"] for r in rs),
                        statistics.median(r["job_s"] for r in rs),
                        round(statistics.median(r["peak_bytes"] for r in rs) / 2**20),
                        rs[0]["cpus"],
                        rs[0]["mem_limit"],
                        ENGINE_MEMORY[engine],
                        rs[0]["outputs_equal"],
                    ]
                )


if __name__ == "__main__":
    main([int(s) for s in sys.argv[1:]] or [1, 10, 100])
