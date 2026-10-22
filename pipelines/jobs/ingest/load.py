from __future__ import annotations

from collections.abc import Callable
from dataclasses import asdict
from typing import TYPE_CHECKING

import fabric_control as fc
from fabric_control.clients.http import HttpError
from fabric_control.contracts import columns, load_schema
from fabric_control.models import GateFailed
from fabric_control.run import Run
from pipelines import io
from pipelines.io.raw import new_load_id
from pipelines.io.sources import Extract
from pipelines.jobs.ingest.reconciliation import (
    LoadCheck,
    compare_schema,
    load_baselines,
    profile,
    reconcile,
    schema_drift,
)
from sources.faults import active_fault

if TYPE_CHECKING:
    from pyspark.sql import DataFrame


def ingest_load(
    run: Run,
    dataset_id: str,
    source_df: DataFrame,
    source: str,
    source_version: int,
    baselines: dict[str, int] | None = None,
    typed: bool = True,
    load_kind: str = "snapshot",
) -> LoadCheck:
    from pyspark.sql import functions as F

    baselines = load_baselines() if baselines is None else baselines
    contract = load_schema(dataset_id)
    expected = columns(contract)
    load_id = new_load_id()
    run.step = f"schema_gate {dataset_id}"
    actual = {f.name: f.dataType.simpleString() if typed else None for f in source_df.schema.fields}
    diff = compare_schema(expected, actual)
    if diff.drift:
        check = schema_drift(load_id, dataset_id, source_df.count(), baselines.get(dataset_id), diff)
        io.ops.write_reconciliation(asdict(check), run.run_id)
        raise GateFailed(f"{dataset_id}: {check.reason}")
    if diff.extra:
        run.warn(f"{dataset_id}: source columns {diff.extra} not in contract {contract['schema_version']}, ignored")
    run.step = f"profile_source {dataset_id}"
    source_df = source_df.select(*[F.col(name).cast(kind).alias(name) for name, kind in expected]).cache()
    source_profile = profile(source_df)
    run.step = f"append_raw {dataset_id}"
    io.append_raw(
        dataset_id, source_df, run.run_id, source, load_kind, source_version, contract["schema_version"], load_id
    )
    run.delta_version = io.delta_version(dataset_id)
    run.step = f"reconcile {dataset_id}"
    raw_profile = profile(io.read_delta(dataset_id).filter(F.col("_load_id") == load_id))
    check = reconcile(load_id, dataset_id, source_profile, raw_profile, baselines.get(dataset_id))
    io.ops.write_reconciliation(asdict(check), run.run_id)
    run.rows_in = (run.rows_in or 0) + source_profile.rows
    run.rows_out = (run.rows_out or 0) + raw_profile.rows
    run.step = None
    source_df.unpersist()
    return check


def run_ingest(job_id: str, source: str, extracts: dict[str, Callable[[], Extract]]) -> list[LoadCheck]:
    baselines = load_baselines()
    checks = []
    with fc.run(job_id, {"mode": "full"}) as run:
        run.step = f"connect {source}"
        cause = active_fault(source)
        if cause:
            raise ConnectionError(f"{source}: {cause}")
        for dataset_id, extract in extracts.items():
            run.step = f"extract {dataset_id}"
            data = extract()
            checks.append(ingest_load(run, dataset_id, data.df, source, data.version, baselines, data.typed))
        for dataset_id in extracts:
            try:
                fc.register(dataset_id)
            except (HttpError, OSError) as e:
                run.warn(f"{dataset_id}: catalog registration failed: {e}")
        failed = [f"{c.dataset_id}: {c.reason}" for c in checks if not c.passed]
        if failed:
            raise GateFailed("reconciliation failed: " + "; ".join(failed))
    return checks
