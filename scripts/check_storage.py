import sys

from delta.tables import DeltaTable

from pipelines import io
from pipelines.io.storage import ensure_bucket, table_path

UNIFIED = "_check/unified"
RAW = "raw/_check/events"


def check(name: str, ok: bool) -> bool:
    print(f"{'ok' if ok else 'FAIL'} {name}")
    return ok


def main() -> int:
    ensure_bucket()
    spark = io.get_spark("check_storage")
    rows = [(1, "north"), (2, "south"), (3, "north")]
    results = []

    io.write_delta(UNIFIED, spark.createDataFrame(rows, "id INT, region STRING"), "check:0")
    results.append(check("write", io.read_delta(UNIFIED).count() == 3))
    first = DeltaTable.forPath(spark, table_path(UNIFIED)).history(1).collect()[0].version

    io.write_delta(UNIFIED, spark.createDataFrame(rows + [(4, "east")], "id INT, region STRING"), "check:1")
    results.append(check("overwrite", io.read_delta(UNIFIED).count() == 4))

    scope = {"mode": "scope", "keys": {"region": ["north"]}}
    io.write_delta(UNIFIED, spark.createDataFrame([(9, "north")], "id INT, region STRING"), "check:2", scope)
    regions = {
        r.region: r.n
        for r in io.read_delta(UNIFIED).groupBy("region").count().withColumnRenamed("count", "n").collect()
    }
    results.append(check("replaceWhere", regions == {"north": 1, "south": 1, "east": 1}))

    results.append(check("time travel", io.read_delta(UNIFIED, version=first).count() == 3))

    spark.conf.set("spark.databricks.delta.retentionDurationCheck.enabled", "false")
    io.vacuum(UNIFIED, retention_hours=0)
    results.append(check("vacuum", io.read_delta(UNIFIED).count() == 3))

    before = io.read_delta(RAW).count() if DeltaTable.isDeltaTable(spark, table_path(RAW)) else 0
    io.write_delta(RAW, spark.createDataFrame(rows, "id INT, region STRING"), "check:raw")
    results.append(check("raw append", io.read_delta(RAW).count() == before + 3))

    spark.stop()
    return 0 if all(results) else 1


if __name__ == "__main__":
    sys.exit(main())
