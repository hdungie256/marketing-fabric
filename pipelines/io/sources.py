from __future__ import annotations

import csv
import io
import json
import os
import urllib.request
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from pipelines.io.spark import get_spark

if TYPE_CHECKING:
    from pyspark.sql import DataFrame


@dataclass(frozen=True)
class Extract:
    df: DataFrame
    version: int
    typed: bool


def sources_dsn() -> dict[str, Any]:
    from psycopg.conninfo import conninfo_to_dict

    return conninfo_to_dict(os.environ["SOURCES_DB_DSN"])


def db_version(source: str) -> int:
    import psycopg

    with psycopg.connect(os.environ["SOURCES_DB_DSN"]) as conn:
        row = conn.execute("SELECT version FROM meta.source_versions WHERE source = %s", (source,)).fetchone()
    if not row:
        raise LookupError(f"source {source} has never been seeded")
    return row[0]


def read_db(source: str, table: str) -> Extract:
    dsn = sources_dsn()
    df = (
        get_spark()
        .read.format("jdbc")
        .option("url", f"jdbc:postgresql://{dsn['host']}:{dsn.get('port', 5432)}/{dsn['dbname']}")
        .option("dbtable", f"{source}.{table}")
        .option("user", dsn["user"])
        .option("password", dsn["password"])
        .option("driver", "org.postgresql.Driver")
        .load()
    )
    return Extract(df, db_version(source), True)


def string_frame(rows: list[dict[str, Any]], columns: list[str]) -> DataFrame:
    from pyspark.sql.types import StringType, StructField, StructType

    schema = StructType([StructField(c, StringType()) for c in columns])
    data = [[None if row.get(c) is None else str(row[c]) for c in columns] for row in rows]
    return get_spark().createDataFrame(data, schema)


def read_api(source: str, table: str) -> Extract:
    url = f"{os.environ['API_URL'].rstrip('/')}/{source}/{table}"
    with urllib.request.urlopen(url, timeout=60) as response:
        body = json.loads(response.read())
    items = body["items"]
    return Extract(string_frame(items, list(items[0]) if items else []), int(body["source_version"]), False)


def read_csv(source: str, table: str) -> Extract:
    import boto3

    s3 = boto3.client("s3", endpoint_url=os.environ["S3_ENDPOINT"], region_name="us-east-1")
    obj = s3.get_object(Bucket=os.environ.get("SOURCES_BUCKET", "sources"), Key=f"{source}/{table}.csv")
    reader = csv.DictReader(io.StringIO(obj["Body"].read().decode()))
    rows = list(reader)
    return Extract(string_frame(rows, list(reader.fieldnames or [])), int(obj["Metadata"]["source-version"]), False)
