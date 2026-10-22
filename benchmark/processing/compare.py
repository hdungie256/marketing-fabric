"""Check that Spark and Flink produced identical orders and RFM rows (Story 9.1).

Usage: python -m benchmark.processing.compare <spark_out> <flink_out>; exits 1 on any difference.
"""

from __future__ import annotations

import sys
from pathlib import Path

ORDERS = (
    "order_key STRING, customer_id BIGINT, transaction_id BIGINT, order_date DATE, gross_value DECIMAL(38,2), "
    "shipping_fee DECIMAL(18,2), line_count INT"
)
RFM = (
    "customer_id BIGINT, recency_days INT, recency_score INT, frequency_orders INT, frequency_score INT, "
    "monetary_value DECIMAL(38,2), monetary_score INT, segment STRING, categories STRING, gender STRING, "
    "location STRING, tenure_months INT"
)


def differences(spark, a: Path, b: Path, schema: str) -> tuple[int, int, int]:
    left = spark.read.csv(str(a), schema=schema)
    right = spark.read.csv(str(b), schema=schema)
    return left.count(), left.exceptAll(right).count(), right.exceptAll(left).count()


def main(spark_out: Path, flink_out: Path) -> int:
    from pyspark.sql import SparkSession

    spark = SparkSession.builder.master("local[2]").config("spark.sql.session.timeZone", "UTC").getOrCreate()
    failed = False
    for name, schema in (("orders", ORDERS), ("rfm", RFM)):
        rows, only_spark, only_flink = differences(spark, spark_out / name, flink_out / name, schema)
        print(f"{name}: {rows} rows, {only_spark} only in Spark, {only_flink} only in Flink")
        failed |= bool(only_spark or only_flink) or rows == 0
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main(Path(sys.argv[1]), Path(sys.argv[2])))
