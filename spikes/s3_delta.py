import json
import time

from pyspark.sql import functions as F

from pipelines.io import read_delta, vacuum, write_delta
from pipelines.io.spark import get_spark
from pipelines.io.storage import ensure_bucket, table_path

DATASET = "spike/s3_delta"
results: dict[str, str] = {}


def step(name, fn):
    try:
        fn()
        results[name] = "pass"
    except Exception as e:
        results[name] = f"fail: {type(e).__name__}: {str(e)[:300]}"
    print(name, results[name], flush=True)


def rows(day, n, value):
    return get_spark().range(n).select(F.lit(day).alias("day"), F.col("id").alias("k"), F.lit(value).alias("v"))


def write():
    write_delta(DATASET, rows("2019-01-01", 5, 1).unionByName(rows("2019-01-02", 5, 1)), "spike:1")
    assert read_delta(DATASET).count() == 10


def overwrite():
    write_delta(DATASET, rows("2019-01-01", 3, 2).unionByName(rows("2019-01-02", 3, 2)), "spike:2")
    assert read_delta(DATASET).count() == 6


def replace_where():
    scope = {"mode": "scope", "keys": {"day": ["2019-01-02"]}}
    write_delta(DATASET, rows("2019-01-02", 4, 3), "spike:3", replace_where=scope)
    df = read_delta(DATASET)
    assert df.filter("day = '2019-01-01'").agg(F.max("v")).first()[0] == 2
    assert df.filter("day = '2019-01-02'").count() == 4
    assert df.filter("day = '2019-01-02'").agg(F.min("v")).first()[0] == 3


def time_travel():
    assert read_delta(DATASET, version=0).count() == 10
    assert read_delta(DATASET, version=1).count() == 6


def vacuum_step():
    spark = get_spark()
    spark.conf.set("spark.databricks.delta.retentionDurationCheck.enabled", "false")
    vacuum(DATASET, 0)
    assert read_delta(DATASET).count() == 7
    try:
        read_delta(DATASET, version=0).select("v").collect()
    except Exception:
        return
    raise AssertionError("version 0 still readable after vacuum")


def append_raw():
    raw = "raw/spike/s3_delta"
    write_delta(raw, rows("2019-01-01", 2, 1), "spike:4")
    write_delta(raw, rows("2019-01-01", 2, 1), "spike:5")
    assert read_delta(raw).count() == 4


if __name__ == "__main__":
    start = time.time()
    step("ensure_bucket", ensure_bucket)
    spark = get_spark("spike_s3_delta")
    from delta.tables import DeltaTable

    for path in (table_path(DATASET), table_path("raw/spike/s3_delta")):
        if DeltaTable.isDeltaTable(spark, path):
            spark.sparkContext._jvm.org.apache.hadoop.fs.Path(path).getFileSystem(
                spark.sparkContext._jsc.hadoopConfiguration()
            ).delete(spark.sparkContext._jvm.org.apache.hadoop.fs.Path(path), True)
    for name, fn in [
        ("write", write),
        ("overwrite", overwrite),
        ("replace_where", replace_where),
        ("time_travel", time_travel),
        ("vacuum", vacuum_step),
        ("append_raw", append_raw),
    ]:
        step(name, fn)
    print(json.dumps({"results": results, "seconds": round(time.time() - start, 1)}))
