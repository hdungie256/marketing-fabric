from pyspark.sql import functions as F

from pipelines.io import read_delta, write_delta
from pipelines.io.result import write_result
from pipelines.io.spark import get_spark
from pipelines.io.storage import ensure_bucket

OUTPUTS = []
DATASET = "_smoke/platform"

if __name__ == "__main__":
    ensure_bucket()
    write_delta(DATASET, get_spark("smoke").range(3).withColumn("ok", F.lit(True)), "smoke")
    write_result({"rows": read_delta(DATASET).count()})
