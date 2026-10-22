"""SeaweedFS vs MinIO vs local FS under the same Delta workload (Story 9.2).

Each run starts a fresh storage server (same 1g limit as the core stack) on a private network, runs storage_job in
a limited fabric-jobs container, then reads the server's cgroup memory.peak. Usage: python benchmark/storage/run.py
"""

from __future__ import annotations

import csv
import os
import statistics
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from benchmark.measure import ROOT, run  # noqa: E402

DATA = ROOT / "benchmark" / "data"
RESULTS = ROOT / "benchmark" / "results"
NETWORK = "fabric-bench"
KEY, SECRET = "bench", "bench-secret-key"
JOBS = "marketing-fabric/fabric-jobs:latest"
SERVERS = {
    "seaweedfs": {
        "image": "chrislusf/seaweedfs:4.47",
        "args": [
            "--entrypoint",
            "/bin/sh",
            "chrislusf/seaweedfs:4.47",
            "-c",
            f'printf \'{{"identities":[{{"name":"b","credentials":[{{"accessKey":"{KEY}",'
            f'"secretKey":"{SECRET}"}}],"actions":["Admin","Read","Write","List","Tagging"]}}]}}\''
            " > /tmp/s3.json && exec weed server -dir=/data -volume.max=0 -master.volumeSizeLimitMB=1024"
            " -s3.concurrentFileUploadLimit=2 -s3 -s3.port=8333 -s3.config=/tmp/s3.json",
        ],
        "endpoint": "http://bench-seaweedfs:8333",
        "ready": "http://localhost:18333/",
        "port": "18333:8333",
    },
    "minio": {
        "image": "marketing-fabric/minio:RELEASE.2025-10-15T17-29-55Z",
        "args": [
            "-e",
            f"MINIO_ROOT_USER={KEY}",
            "-e",
            f"MINIO_ROOT_PASSWORD={SECRET}",
            "marketing-fabric/minio:RELEASE.2025-10-15T17-29-55Z",
            "server",
            "/data",
        ],
        "endpoint": "http://bench-minio:9000",
        "ready": "http://localhost:19000/minio/health/live",
        "port": "19000:9000",
    },
}
RUNS = 3


def start(name: str) -> float:
    spec = SERVERS[name]
    subprocess.run(["docker", "rm", "-f", f"bench-{name}"], capture_output=True)
    started = time.perf_counter()
    subprocess.run(
        [
            "docker",
            "run",
            "-d",
            "--name",
            f"bench-{name}",
            "--network",
            NETWORK,
            "--memory=1g",
            "-p",
            spec["port"],
            *spec["args"],
        ],
        check=True,
        capture_output=True,
    )
    while True:
        try:
            urllib.request.urlopen(spec["ready"], timeout=1)
            return round(time.perf_counter() - started, 2)
        except OSError as e:
            if getattr(e, "code", None) == 403:  # SeaweedFS S3 answers anonymous GET / with 403 once it is up
                return round(time.perf_counter() - started, 2)
            time.sleep(0.2)


def peak(name: str) -> int:
    out = subprocess.run(
        ["docker", "exec", f"bench-{name}", "cat", "/sys/fs/cgroup/memory.peak"],
        capture_output=True,
        text=True,
        check=True,
    )
    return int(out.stdout)


def main() -> None:
    subprocess.run(["docker", "network", "create", NETWORK], capture_output=True)
    rows = []
    for backend in ("seaweedfs", "minio", "local"):
        for attempt in range(1, RUNS + 1):
            env = []
            startup = server_peak = None
            if backend == "local":
                root = "file:///tmp/delta"
            else:
                startup = start(backend)
                root = "s3a://bench"
                env = [
                    "-e",
                    f"S3_ENDPOINT={SERVERS[backend]['endpoint']}",
                    "-e",
                    "S3_BUCKET=bench",
                    "-e",
                    f"AWS_ACCESS_KEY_ID={KEY}",
                    "-e",
                    f"AWS_SECRET_ACCESS_KEY={SECRET}",
                ]
            result = run(
                JOBS,
                ["python", "-m", "benchmark.storage.storage_job", "/bench/x10", root],
                DATA,
                extra=["--network", NETWORK, *env],
            )
            if backend != "local":
                server_peak = peak(backend)
                subprocess.run(["docker", "rm", "-f", f"bench-{backend}"], capture_output=True)
            row = {
                "backend": backend,
                "run": attempt,
                "startup_s": startup,
                "server_peak_mib": server_peak and round(server_peak / 2**20),
                "job_peak_mib": round(result["peak_bytes"] / 2**20),
                "total_s": result["job_s"],
                "rows": result["rows"],
                **result["steps"],
            }
            print(row, flush=True)
            rows.append(row)
    RESULTS.mkdir(exist_ok=True)
    fields = list(rows[0])
    with (RESULTS / "storage_runs.csv").open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)
    with (RESULTS / "storage.csv").open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["backend", *[k for k in fields if k not in ("backend", "run")]])
        for backend in ("seaweedfs", "minio", "local"):
            rs = [r for r in rows if r["backend"] == backend]
            w.writerow(
                [
                    backend,
                    *[
                        statistics.median(r[k] for r in rs) if rs[0][k] is not None else ""
                        for k in fields
                        if k not in ("backend", "run")
                    ],
                ]
            )
    print(f"data: x10, {os.path.basename(str(DATA))}")


if __name__ == "__main__":
    main()
