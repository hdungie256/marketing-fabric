"""Run one benchmark command in a fresh, resource-limited container and capture wall time and peak memory.

Shared by Stories 9.1-9.3. The command prints `RESULT {json}` (see processing/common.report); the container's
cgroup memory.peak covers every process in it, the JVM included.
"""

from __future__ import annotations

import json
import subprocess
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CPUS = "2"
MEMORY = "4g"


def run(
    image: str, command: list[str], data: Path, cpus: str = CPUS, memory: str = MEMORY, extra: list[str] | None = None
) -> dict:
    docker = [
        "docker",
        "run",
        "--rm",
        f"--cpus={cpus}",
        f"--memory={memory}",
        "-v",
        f"{ROOT}:/srv:ro",
        "-v",
        f"{data}:/bench",
        "-w",
        "/srv",
        "-e",
        "PYTHONPATH=/srv",
        *(extra or []),
        image,
        *command,
    ]
    started = time.perf_counter()
    done = subprocess.run(docker, capture_output=True, text=True)
    wall = round(time.perf_counter() - started, 2)
    lines = [line for line in done.stdout.splitlines() if line.startswith("RESULT ")]
    if done.returncode or not lines:
        raise RuntimeError(
            f"{' '.join(command)} failed ({done.returncode}):\n{done.stdout[-2000:]}\n{done.stderr[-4000:]}"
        )
    return {**json.loads(lines[-1].removeprefix("RESULT ")), "wall_s": wall, "cpus": cpus, "mem_limit": memory}
