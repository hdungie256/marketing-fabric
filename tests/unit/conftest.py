import pytest


@pytest.fixture(scope="module")
def spark():
    sql = pytest.importorskip("pyspark.sql")
    session = sql.SparkSession.builder.master("local[1]").appName("unit").getOrCreate()
    yield session
    session.stop()
