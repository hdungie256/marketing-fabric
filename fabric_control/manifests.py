from pathlib import Path
from typing import Any

import yaml

from fabric_control.config import jobs_dir

PATTERNS = ("mart*.yml", "manifest*.yml")


class ManifestError(Exception):
    pass


def load_manifests(directory: Path | None = None) -> dict[str, dict[str, Any]]:
    directory = directory or jobs_dir()
    manifests: dict[str, dict[str, Any]] = {}
    paths = sorted(p for pattern in PATTERNS for p in directory.rglob(pattern) if "_templates" not in p.parts)
    for path in paths:
        data = yaml.safe_load(path.read_text()) or {}
        table = data.get("table")
        if not table:
            continue
        if table in manifests:
            raise ManifestError(f"{table} has two manifests, the second in {path}")
        unknown = sorted(set((data.get("scope_map") or {}).values()) - set(data.get("grain") or []))
        if unknown:
            raise ManifestError(f"{path}: scope_map targets {unknown} are not grain columns")
        manifests[table] = data
    return manifests
