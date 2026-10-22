"""OpenMetadata vs Unity Catalog OSS: startup, memory and catalog operations (Story 9.2).

OpenMetadata runs as in the core stack (server + Elasticsearch + Postgres, started with docker compose);
Unity Catalog OSS runs as one container. Usage: python benchmark/catalog/run.py → benchmark/results/catalog.csv
"""

from __future__ import annotations

import csv
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from benchmark.measure import ROOT, run  # noqa: E402

RESULTS = ROOT / "benchmark" / "results"
COMPOSE = ["docker", "compose", "-f", str(ROOT / "compose" / "docker-compose.yml")]
OM_SERVICES = ["openmetadata-server", "elasticsearch"]
JOBS = "marketing-fabric/fabric-jobs:latest"
UC_IMAGE = "unitycatalog/unitycatalog:v0.6.0"


def env_file() -> dict[str, str]:
    lines = (ROOT / "compose" / ".env").read_text().splitlines()
    return dict(line.split("=", 1) for line in lines if "=" in line and not line.startswith("#"))


def peak(container: str) -> int:
    out = subprocess.run(
        ["docker", "exec", container, "cat", "/sys/fs/cgroup/memory.peak"], capture_output=True, text=True, check=True
    )
    return int(out.stdout)


def wait(check) -> None:
    while not check():
        time.sleep(1)


def healthy(container: str) -> bool:
    out = subprocess.run(
        ["docker", "inspect", "-f", "{{.State.Health.Status}}", container], capture_output=True, text=True
    )
    return out.stdout.strip() == "healthy"


def openmetadata() -> dict:
    env = env_file()
    subprocess.run([*COMPOSE, "stop", *OM_SERVICES], capture_output=True)
    subprocess.run([*COMPOSE, "rm", "-f", *OM_SERVICES], capture_output=True)  # fresh cgroups for memory.peak
    started = time.perf_counter()
    subprocess.run([*COMPOSE, "up", "-d", "openmetadata-server"], check=True, capture_output=True)
    wait(lambda: healthy("marketing-fabric-openmetadata-server-1"))
    startup = round(time.perf_counter() - started, 2)
    job_env = {
        "FABRIC_CONTROL_MODE": "online",
        "OM_URL": "http://openmetadata-server:8585/api",
        "OM_ADMIN_USER": env["OM_ADMIN_USER"],
        "OM_ADMIN_PASSWORD": env["OM_ADMIN_PASSWORD"],
        "OM_BOT_TOKEN_FILE": "/tmp/bot_token",
        "S3_ENDPOINT": "http://seaweedfs:8333",
        "S3_BUCKET": "lake",
        "AWS_ACCESS_KEY_ID": "unused",
        "AWS_SECRET_ACCESS_KEY": "unused",
    }
    flags = ["--network", "marketing-fabric_default", *[x for k, v in job_env.items() for x in ("-e", f"{k}={v}")]]
    result = run(
        JOBS, ["python", "-m", "benchmark.catalog.catalog_job", "om"], ROOT / "benchmark" / "data", extra=flags
    )
    peaks = {s: peak(f"marketing-fabric-{s}-1") for s in OM_SERVICES}
    subprocess.run([*COMPOSE, "stop", *OM_SERVICES], capture_output=True)
    return {
        "catalog": "openmetadata 2.0.2",
        "containers": "server + elasticsearch (+ shared postgres)",
        "startup_s": startup,
        "peak_mib": round(sum(peaks.values()) / 2**20),
        **result["steps"],
        **{k: result[k] for k in ("tables", "edges", "query_hits")},
    }


def unity() -> dict:
    subprocess.run(["docker", "rm", "-f", "bench-uc"], capture_output=True)
    subprocess.run(["docker", "network", "create", "fabric-bench"], capture_output=True)
    started = time.perf_counter()
    subprocess.run(
        ["docker", "run", "-d", "--name", "bench-uc", "--network", "fabric-bench", "-p", "18080:8080", UC_IMAGE],
        check=True,
        capture_output=True,
    )

    def ready() -> bool:
        try:
            urllib.request.urlopen("http://localhost:18080/api/2.1/unity-catalog/catalogs", timeout=1)
            return True
        except OSError:
            return False

    wait(ready)
    startup = round(time.perf_counter() - started, 2)
    flags = ["--network", "fabric-bench", "-e", "UC_URL=http://bench-uc:8080/api/2.1/unity-catalog"]
    result = run(
        JOBS, ["python", "-m", "benchmark.catalog.catalog_job", "uc"], ROOT / "benchmark" / "data", extra=flags
    )
    memory = peak("bench-uc")
    subprocess.run(["docker", "rm", "-f", "bench-uc"], capture_output=True)
    return {
        "catalog": "unity catalog oss v0.6.0",
        "containers": "server (embedded H2)",
        "startup_s": startup,
        "peak_mib": round(memory / 2**20),
        **result["steps"],
        **{k: result[k] for k in ("tables", "edges", "query_hits")},
    }


def main() -> None:
    rows = []
    for measure in (openmetadata, unity):
        rows.append(measure())
        print(rows[-1], flush=True)
    RESULTS.mkdir(exist_ok=True)
    with (RESULTS / "catalog.csv").open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)


if __name__ == "__main__":
    main()
