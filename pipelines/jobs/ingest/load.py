from __future__ import annotations

from dataclasses import asdict
from typing import TYPE_CHECKING

from fabric_control.run import Run
from pipelines import io
from pipelines.jobs.ingest.reconciliation import LoadCheck, load_baselines, profile, reconcile

if TYPE_CHECKING:
    from pyspark.sql import DataFrame


def ingest_load(
    run: Run,
    dataset_id: str,
    source_df: DataFrame,
    source: str,
    load_kind: str,
    source_version: int,
    baselines: dict[str, int] | None = None,
) -> LoadCheck:
    from pyspark.sql import functions as F

    baselines = load_baselines() if baselines is None else baselines
    run.step = f"profile_source {dataset_id}"
    source_df = source_df.cache()
    source_profile = profile(source_df)
    run.step = f"append_raw {dataset_id}"
    load_id = io.append_raw(dataset_id, source_df, run.run_id, source, load_kind, source_version)
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
