"""Delta Lake workload against one storage backend (Story 9.2).

Usage: python -m benchmark.storage.storage_job <data_dir> <root_uri>
root_uri is s3a://bench (SeaweedFS or MinIO, via S3_ENDPOINT) or file:///tmp/delta (local FS).
The steps mirror what the platform does: full write, scan, replaceWhere, small raw appends, time travel.
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

from benchmark.processing.common import PARALLELISM, report
from benchmark.processing.spark_job import LINES

APPENDS = 10


def session(root: str):
    from pyspark.sql import SparkSession

    from pipelines.io.spark import s3_conf

    builder = (
        SparkSession.builder.master(f"local[{PARALLELISM}]")
        .config("spark.driver.memory", "2g")
        .config("spark.sql.extensions", "io.delta.sql.DeltaSparkSessionExtension")
        .config("spark.sql.catalog.spark_catalog", "org.apache.spark.sql.delta.catalog.DeltaCatalog")
    )
    if root.startswith("s3a://"):
        for key, value in s3_conf().items():
            builder = builder.config(key, value)
    return builder.getOrCreate()


def main(data: Path, root: str) -> None:
    from pyspark.sql import functions as F

    if root.startswith("s3a://"):
        from pipelines.io.storage import ensure_bucket

        ensure_bucket()
    spark = session(root)
    path = f"{root}/lines"
    lines = spark.read.csv(str(data / "lines.csv"), schema=LINES).cache()
    lines.count()
    steps = {}
    started = time.perf_counter()

    def step(name: str, action) -> None:
        t = time.perf_counter()
        action()
        steps[name] = round(time.perf_counter() - t, 2)

    step("write", lambda: lines.write.format("delta").mode("overwrite").save(path))
    step("scan", lambda: spark.read.format("delta").load(path).groupBy("customer_id").agg(F.sum("quantity")).count())
    january = "transaction_date_iso < '2019-02-01'"
    step(
        "replace_where",
        lambda: (
            lines.filter(january).write.format("delta").mode("overwrite").option("replaceWhere", january).save(path)
        ),
    )
    batch = lines.limit(1000).cache()
    batch.count()
    step("appends", lambda: [batch.write.format("delta").mode("append").save(path) for _ in range(APPENDS)])
    step("time_travel", lambda: spark.read.format("delta").option("versionAsOf", 0).load(path).count())
    rows = spark.read.format("delta").load(path).count()
    report("storage", data, started, root=root, steps=steps, rows=rows)
    spark.stop()


if __name__ == "__main__":
    main(Path(sys.argv[1]), sys.argv[2])
