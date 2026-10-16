"""Glossary and tags as code (Story 2.1, FR-11, AD-16).

Pure file-side logic: merge per-slice fragments, validate, derive term IDs,
and COMPUTE synthetic provenance by propagating from synthetic raw sources
through the job graph. No OpenMetadata or Spark imports here, so this module
stays usable in offline/dev mode and unit tests.

Provenance roots are raw datasets flagged `synthetic_source: true` in the
registry (grounded in `sources/seed.py`: wholly-synthetic seed tables and
per-row synthetic sources per R16). Everything downstream is derived, never
hand-assigned (AD-2).
"""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any

import yaml

from fabric_control.contracts import ContractError, columns, load_schema
from fabric_control.registry import load_registry

ROOT = Path(__file__).resolve().parent.parent

GLOSSARY_NAME = "marketing_metrics"

REQUIRED_TERM_FIELDS = (
    "display_name",
    "owner_slice",
    "dataset_id",
    "column",
    "definition",
    "formula",
    "rules",
    "limitations",
    "notes",
)
REQUIRED_TAG_FIELDS = ("name", "classification", "description")


class GlossaryError(Exception):
    pass


def governance_dir() -> Path:
    return Path(os.environ.get("FABRIC_GOVERNANCE_DIR", ROOT / "governance"))


def term_id(display_name: str) -> str:
    """AD-16: snake_case of the display name with `/` -> `_per_`."""
    slug = re.sub(r"[^a-z0-9]+", "_", display_name.lower().replace("/", "_per_")).strip("_")
    if not slug:
        raise GlossaryError(f"display_name {display_name!r} yields an empty term id")
    return slug


def _fragments(subdir: str, key: str, directory: Path | None = None) -> list[tuple[str, list[dict[str, Any]]]]:
    base = directory or governance_dir()
    found = []
    for path in sorted((base / subdir).glob("*.yml")):
        doc = yaml.safe_load(path.read_text()) or {}
        items = doc.get(key) or []
        if not isinstance(items, list):
            raise GlossaryError(f"{path.name}: {key} must be a list")
        found.append((path.name, items))
    return found


def load_terms(directory: Path | None = None, registry: dict[str, dict] | None = None) -> dict[str, dict[str, Any]]:
    """Merge glossary fragments; fail on duplicates or dangling column links."""
    registry = registry if registry is not None else load_registry()
    terms: dict[str, dict[str, Any]] = {}
    for filename, items in _fragments("glossary", "terms", directory):
        for item in items:
            missing = [f for f in REQUIRED_TERM_FIELDS if f not in item]
            if missing:
                raise GlossaryError(f"{filename}: term {item.get('display_name')!r} missing {missing}")
            tid = term_id(item["display_name"])
            if tid in terms:
                raise GlossaryError(
                    f"duplicate term {item['display_name']!r} (id {tid!r}) in {terms[tid]['_file']} and {filename}"
                )
            for field in ("rules", "limitations", "notes"):
                if not isinstance(item[field], list):
                    raise GlossaryError(f"{filename}: term {tid!r} field {field} must be a list")
                bad = [v for v in item[field] if not isinstance(v, str)]
                if bad:
                    raise GlossaryError(
                        f"{filename}: term {tid!r} field {field} items must be strings "
                        f"(quote '- key: value' lines), got {bad!r}"
                    )
            if item["dataset_id"] not in registry:
                raise GlossaryError(f"{filename}: term {tid!r} links unregistered dataset {item['dataset_id']!r}")
            try:
                names = {name for name, _ in columns(load_schema(item["dataset_id"]))}
            except ContractError as e:
                raise GlossaryError(f"{filename}: term {tid!r} has no schema contract: {e}") from e
            if item["column"] not in names:
                raise GlossaryError(
                    f"{filename}: term {tid!r} links unknown column {item['dataset_id']}.{item['column']!r}"
                )
            terms[tid] = {**item, "term_id": tid, "_file": filename}
    return terms


def load_tags(directory: Path | None = None) -> dict[tuple[str, str], dict[str, Any]]:
    """Merge tag fragments keyed by (classification, name)."""
    tags: dict[tuple[str, str], dict[str, Any]] = {}
    origins: dict[tuple[str, str], str] = {}
    for filename, items in _fragments("tags", "tags", directory):
        for item in items:
            missing = [f for f in REQUIRED_TAG_FIELDS if f not in item]
            if missing:
                raise GlossaryError(f"{filename}: tag {item.get('name')!r} missing {missing}")
            key = (item["classification"], item["name"])
            if key in tags:
                raise GlossaryError(f"duplicate tag {key[0]}.{key[1]} in {origins[key]} and {filename}")
            tags[key] = {**item, "_file": filename}
            origins[key] = filename
    return tags


def synthetic_roots(registry: dict[str, dict] | None = None) -> set[str]:
    """Raw datasets whose source provenance is synthetic (registry-flagged roots)."""
    registry = registry if registry is not None else load_registry()
    return {d for d, e in registry.items() if d.startswith("raw/") and e.get("synthetic_source")}


def synthetic_closure(registry: dict[str, dict] | None = None, root: Path | None = None) -> set[str]:
    """All datasets derived from a synthetic root (fixpoint over job inputs).

    A dataset is synthetic iff its writer job reads a synthetic input; ingest
    jobs have no dataset inputs so multi-output sources never leak synthetic
    labels onto original siblings.
    """
    from pipelines.dags.job_graph import declared, writers

    registry = registry if registry is not None else load_registry()
    root = root or ROOT
    dataset_writers = writers(root)

    def inputs_of(job_id: str) -> list[str]:
        path = root / "pipelines" / "jobs" / job_id / "job.py"
        return declared(path, "INPUTS") if path.exists() else []

    synth = set(synthetic_roots(registry))
    changed = True
    while changed:
        changed = False
        for dataset_id, job_id in dataset_writers.items():
            if dataset_id not in synth and any(i in synth for i in inputs_of(job_id)):
                synth.add(dataset_id)
                changed = True
    return synth


def labelled_terms(
    directory: Path | None = None,
    registry: dict[str, dict] | None = None,
    root: Path | None = None,
) -> dict[str, dict[str, Any]]:
    """Glossary terms with computed `provenance`: `synthetic` or `original`."""
    registry = registry if registry is not None else load_registry()
    terms = load_terms(directory, registry)
    synth = synthetic_closure(registry, root)
    return {
        tid: {**t, "provenance": "synthetic" if t["dataset_id"] in synth else "original"} for tid, t in terms.items()
    }
