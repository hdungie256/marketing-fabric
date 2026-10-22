"""Unified orders + RFM on Spark with the demo's own transforms (Story 9.1).

Usage: python -m benchmark.processing.spark_job <data_dir> <out_dir>
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

from benchmark.processing.common import AS_OF, ORDER_COLUMNS, PARALLELISM, RFM_COLUMNS, SEGMENTS, report

LINES = (
    "customer_id BIGINT, transaction_id BIGINT, transaction_date_iso DATE, product_category STRING, quantity INT, "
    "avg_price DECIMAL(18,2), delivery_charges DECIMAL(18,2), provenance STRING"
)
CUSTOMERS = "customer_id BIGINT, gender STRING, location STRING, tenure_months INT"


def main(data: Path, out: Path) -> None:
    from pyspark.sql import SparkSession
    from pyspark.sql import functions as F

    from pipelines.jobs.marts.customer.rfm.transforms import build_rfm
    from pipelines.jobs.unified._common import canonical_column
    from pipelines.jobs.unified.orders.transforms import build_orders

    spark = (
        SparkSession.builder.master(f"local[{PARALLELISM}]")
        .config("spark.driver.memory", "2g")
        .config("spark.sql.shuffle.partitions", str(PARALLELISM * 4))
        .config("spark.sql.session.timeZone", "UTC")
        .getOrCreate()
    )
    started = time.perf_counter()
    lines = spark.read.csv(str(data / "lines.csv"), schema=LINES)
    lines = canonical_column(lines).withColumn(
        "canonical_order_id", F.concat_ws("_", F.col("customer_id"), F.col("transaction_id"))
    )
    customers = spark.read.csv(str(data / "customers.csv"), schema=CUSTOMERS)
    orders = build_orders(lines).cache()
    rfm = build_rfm(orders, customers, lines, AS_OF, SEGMENTS)
    orders.select(*ORDER_COLUMNS).write.mode("overwrite").csv(str(out / "orders"))
    rfm.select(*RFM_COLUMNS).write.mode("overwrite").csv(str(out / "rfm"))
    report("spark", data, started, spark_version=spark.version, driver_memory="2g")
    spark.stop()


if __name__ == "__main__":
    main(Path(sys.argv[1]), Path(sys.argv[2]))
