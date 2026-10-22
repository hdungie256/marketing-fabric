"""GX vs Soda Core on the same rules and the same Spark frame (Story 9.2).

Usage: python -m benchmark.quality.quality_job <data_dir> <gx|soda> <clean|broken>
`broken` adds a duplicated order_key and a NULL gross_value, so the critical rules must fail.
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

from benchmark.processing.common import PARALLELISM, report
from benchmark.processing.spark_job import LINES

DATASET = "unified/orders"


def orders(spark, data: Path, broken: bool):
    from pyspark.sql import functions as F

    from pipelines.jobs.unified.orders.transforms import build_orders

    lines = spark.read.csv(str(data / "lines.csv"), schema=LINES).withColumn(
        "canonical_order_id", F.concat_ws("_", F.col("customer_id"), F.col("transaction_id"))
    )
    df = build_orders(lines)
    if broken:
        first = df.limit(1)
        df = df.unionByName(first).unionByName(
            first.withColumn("order_key", F.lit("x|1")).withColumn(
                "gross_value", F.lit(None).cast(df.schema["gross_value"].dataType)
            )
        )
    return df.cache()


def gx(df, rules) -> dict[str, bool]:
    from fabric_control.data_quality import validate

    return {r.rule_id: r.passed for r in validate(df, rules)}


def soda(spark, df, rules) -> dict[str, bool]:
    from soda.scan import Scan

    from benchmark.quality.sodacl import checks_yaml

    df.createOrReplaceTempView("orders")
    scan = Scan()
    scan.set_data_source_name("spark_df")
    scan.add_spark_session(spark, data_source_name="spark_df")
    scan.add_sodacl_yaml_str(checks_yaml("orders", rules))
    scan.execute()
    return {c["name"]: c["outcome"] == "pass" for c in scan.get_scan_results()["checks"]}


def main(data: Path, tool: str, mode: str) -> None:
    from pyspark.sql import SparkSession

    from fabric_control.data_quality import load_rules, rules_path

    spark = SparkSession.builder.master(f"local[{PARALLELISM}]").config("spark.driver.memory", "2g").getOrCreate()
    df = orders(spark, data, mode == "broken")
    rows = df.count()  # materialize the cache so only validation is timed
    rules = load_rules(rules_path(DATASET))
    started = time.perf_counter()
    passed = gx(df, rules) if tool == "gx" else soda(spark, df, rules)
    report(tool, data, started, mode=mode, rows=rows, passed=passed)
    spark.stop()


if __name__ == "__main__":
    main(Path(sys.argv[1]), sys.argv[2], sys.argv[3])
