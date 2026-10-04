from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

import yaml

if TYPE_CHECKING:
    from pyspark.sql import DataFrame

ROOT = Path(__file__).resolve().parents[3]


@dataclass(frozen=True)
class Profile:
    rows: int
    checksum: str


@dataclass(frozen=True)
class LoadCheck:
    load_id: str
    dataset_id: str
    source_rows: int
    raw_rows: int
    baseline_rows: int | None
    source_checksum: str
    raw_checksum: str
    passed: bool
    reason: str | None


@dataclass(frozen=True)
class SchemaDiff:
    missing: list[str]
    retyped: list[str]
    extra: list[str]

    @property
    def drift(self) -> bool:
        return bool(self.missing or self.retyped)


def compare_schema(expected: list[tuple[str, str]], actual: dict[str, str | None]) -> SchemaDiff:
    names = dict(expected)
    return SchemaDiff(
        missing=[name for name, _ in expected if name not in actual],
        retyped=[
            f"{name} {actual[name]} != {kind}"
            for name, kind in expected
            if name in actual and actual[name] is not None and actual[name] != kind
        ],
        extra=[name for name in actual if name not in names],
    )


def schema_drift(load_id: str, dataset_id: str, source_rows: int, baseline: int | None, diff: SchemaDiff) -> LoadCheck:
    details = [f"missing {diff.missing}" if diff.missing else "", f"retyped {diff.retyped}" if diff.retyped else ""]
    return LoadCheck(
        load_id=load_id,
        dataset_id=dataset_id,
        source_rows=source_rows,
        raw_rows=0,
        baseline_rows=baseline,
        source_checksum="",
        raw_checksum="",
        passed=False,
        reason="schema_drift: " + "; ".join(d for d in details if d),
    )


def profile(df: DataFrame) -> Profile:
    from pyspark.sql import functions as F

    columns = sorted(c for c in df.columns if not c.startswith("_"))
    row_hash = F.xxhash64(*[F.col(c) for c in columns]).cast("decimal(38,0)")
    result = df.agg(F.count(F.lit(1)).alias("rows"), F.sum(row_hash).alias("checksum")).first()
    return Profile(result["rows"], str(result["checksum"] or 0))


def reconcile(load_id: str, dataset_id: str, source: Profile, raw: Profile, baseline: int | None) -> LoadCheck:
    reasons = []
    if source.rows != raw.rows:
        reasons.append(f"rows: source {source.rows} != raw {raw.rows}")
    if source.checksum != raw.checksum:
        reasons.append("checksum: source != raw")
    if baseline is not None and raw.rows != baseline:
        reasons.append(f"rows: raw {raw.rows} != baseline {baseline}")
    return LoadCheck(
        load_id=load_id,
        dataset_id=dataset_id,
        source_rows=source.rows,
        raw_rows=raw.rows,
        baseline_rows=baseline,
        source_checksum=source.checksum,
        raw_checksum=raw.checksum,
        passed=not reasons,
        reason="; ".join(reasons) or None,
    )


def load_baselines(path: Path | None = None) -> dict[str, int]:
    path = path or Path(os.environ.get("FABRIC_GOVERNANCE_DIR", ROOT / "governance")) / "baselines.yml"
    if not path.exists():
        return {}
    data = yaml.safe_load(path.read_text()) or {}
    return {dataset_id: int(rows) for dataset_id, rows in (data.get("load_rows") or {}).items()}
