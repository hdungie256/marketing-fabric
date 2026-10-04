import os
import time

import psycopg
from pyspark.sql import functions as F

from pipelines.io import read_delta, write_delta
from pipelines.io.spark import get_spark

ROWS = int(os.environ.get("SPIKE_ROWS", "2000000"))
DATASET = "spike/ram_lines"

if __name__ == "__main__":
    start = time.time()
    spark = get_spark("spike_ram")
    lines = spark.range(ROWS).select(
        (F.col("id") % 1500).alias("customer_id"),
        (F.col("id") % 400).alias("product_id"),
        (F.col("id") % 60).alias("campaign_id"),
        F.date_add(F.lit("2019-01-01"), (F.col("id") % 365).cast("int")).alias("order_date"),
        (F.rand(7) * 500).cast("decimal(18,2)").alias("net_value"),
        F.sha1(F.col("id").cast("string")).alias("transaction_id"),
    )
    write_delta(DATASET, lines, "spike:ram")
    daily = (
        read_delta(DATASET)
        .groupBy("campaign_id", "order_date")
        .agg(F.sum("net_value").alias("revenue"), F.countDistinct("customer_id").alias("buyers"))
    )
    info = psycopg.conninfo.conninfo_to_dict(os.environ["SERVING_DB_DSN"])
    with psycopg.connect(os.environ["SERVING_DB_DSN"], autocommit=True) as conn:
        conn.execute("CREATE SCHEMA IF NOT EXISTS spike")
    (
        daily.write.format("jdbc")
        .option("url", f"jdbc:postgresql://{info['host']}:{info.get('port', 5432)}/{info['dbname']}")
        .option("dbtable", "spike.ram_daily")
        .option("user", info["user"])
        .option("password", info["password"])
        .option("driver", "org.postgresql.Driver")
        .mode("overwrite")
        .save()
    )
    print(f"rows={ROWS} daily={daily.count()} seconds={time.time() - start:.1f}", flush=True)
