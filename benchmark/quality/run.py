"""GX vs Soda Core: validation time and verdicts on clean and broken orders at x1, x10, x100 (Story 9.2).

Usage: python benchmark/quality/run.py [scales...] → benchmark/results/quality*.csv
"""

from __future__ import annotations

import csv
import statistics
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from benchmark.measure import ROOT, run  # noqa: E402

DATA = ROOT / "benchmark" / "data"
RESULTS = ROOT / "benchmark" / "results"
IMAGE = "marketing-fabric/quality-bench:latest"
RUNS = 3


def main(scales: list[int]) -> None:
    runs = []
    for scale in scales:
        for mode in ("clean", "broken"):
            for tool in ("gx", "soda"):
                for attempt in range(1, RUNS + 1):
                    r = run(
                        IMAGE, ["python", "-m", "benchmark.quality.quality_job", f"/bench/x{scale}", tool, mode], DATA
                    )
                    row = {
                        "tool": tool,
                        "scale": scale,
                        "mode": mode,
                        "run": attempt,
                        "rows": r["rows"],
                        "validate_s": r["job_s"],
                        "wall_s": r["wall_s"],
                        "peak_mib": round(r["peak_bytes"] / 2**20),
                        "failed_rules": ";".join(sorted(k for k, ok in r["passed"].items() if not ok)),
                    }
                    print(row, flush=True)
                    runs.append(row)
    RESULTS.mkdir(exist_ok=True)
    with (RESULTS / "quality_runs.csv").open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(runs[0]))
        w.writeheader()
        w.writerows(runs)
    with (RESULTS / "quality.csv").open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow(
            [
                "tool",
                "scale",
                "mode",
                "rows",
                "median_validate_s",
                "median_wall_s",
                "median_peak_mib",
                "failed_rules",
                "same_verdict_as_other_tool",
            ]
        )
        for scale in scales:
            for mode in ("clean", "broken"):
                verdicts = {}
                for tool in ("gx", "soda"):
                    rs = [r for r in runs if (r["tool"], r["scale"], r["mode"]) == (tool, scale, mode)]
                    verdicts[tool] = {r["failed_rules"] for r in rs}
                for tool in ("gx", "soda"):
                    rs = [r for r in runs if (r["tool"], r["scale"], r["mode"]) == (tool, scale, mode)]
                    w.writerow(
                        [
                            tool,
                            scale,
                            mode,
                            rs[0]["rows"],
                            statistics.median(r["validate_s"] for r in rs),
                            statistics.median(r["wall_s"] for r in rs),
                            statistics.median(r["peak_mib"] for r in rs),
                            rs[0]["failed_rules"],
                            verdicts["gx"] == verdicts["soda"] and len(verdicts["gx"]) == 1,
                        ]
                    )


if __name__ == "__main__":
    main([int(s) for s in sys.argv[1:]] or [1, 10, 100])
