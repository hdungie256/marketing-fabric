import pytest

from pipelines.io.raw import LOAD_COLUMNS, latest_per_key, stamp
from pipelines.jobs.ingest.reconciliation import profile

pyspark_sql = pytest.importorskip("pyspark.sql")


@pytest.fixture(scope="module")
def spark():
    session = pyspark_sql.SparkSession.builder.master("local[1]").appName("unit").getOrCreate()
    yield session
    session.stop()


def test_latest_per_key_prefers_newest_source_version(spark):
    rows = [(1, "old", 1, "2026-01-01"), (1, "new", 2, "2026-01-01"), (2, "only", 1, "2026-01-01")]
    df = spark.createDataFrame(rows, "id INT, v STRING, _source_version BIGINT, _ingested_at STRING")
    result = {r.id: r.v for r in latest_per_key(df, ["id"]).collect()}
    assert result == {1: "new", 2: "only"}


def test_latest_per_key_breaks_ties_by_ingested_at(spark):
    rows = [(1, "first", 1, "2026-01-01"), (1, "second", 1, "2026-01-02")]
    df = spark.createDataFrame(rows, "id INT, v STRING, _source_version BIGINT, _ingested_at STRING")
    assert [r.v for r in latest_per_key(df, ["id"]).collect()] == ["second"]


def test_profile_ignores_order_and_metadata_columns(spark):
    a = spark.createDataFrame([(1, "x"), (2, "y")], "id INT, v STRING")
    b = stamp(spark.createDataFrame([(2, "y"), (1, "x")], "id INT, v STRING"), "l1", "src", "snapshot", 7, "1.0.0")
    assert profile(a) == profile(b)
    assert profile(a).rows == 2


def test_profile_detects_changed_value(spark):
    a = spark.createDataFrame([(1, "x")], "id INT, v STRING")
    b = spark.createDataFrame([(1, "z")], "id INT, v STRING")
    assert profile(a).checksum != profile(b).checksum


def test_stamp_adds_load_columns(spark):
    df = stamp(spark.createDataFrame([(1,)], "id INT"), "l1", "crm", "snapshot", 3, "1.2.0")
    assert set(LOAD_COLUMNS) <= set(df.columns)
    row = df.first()
    values = (row._load_id, row._source, row._load_kind, row._source_version, row._schema_version)
    assert values == ("l1", "crm", "snapshot", 3, "1.2.0")
