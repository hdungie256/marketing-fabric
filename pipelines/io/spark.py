from __future__ import annotations

import os
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pyspark.sql import SparkSession


def s3_conf() -> dict[str, str]:
    endpoint = os.environ["S3_ENDPOINT"]
    return {
        "spark.hadoop.fs.s3a.impl": "org.apache.hadoop.fs.s3a.S3AFileSystem",
        "spark.hadoop.fs.s3a.endpoint": endpoint,
        "spark.hadoop.fs.s3a.path.style.access": "true",
        "spark.hadoop.fs.s3a.connection.ssl.enabled": str(endpoint.startswith("https")).lower(),
        "spark.hadoop.fs.s3a.aws.credentials.provider": "org.apache.hadoop.fs.s3a.SimpleAWSCredentialsProvider",
        "spark.hadoop.fs.s3a.access.key": os.environ["AWS_ACCESS_KEY_ID"],
        "spark.hadoop.fs.s3a.secret.key": os.environ["AWS_SECRET_ACCESS_KEY"],
    }


def get_spark(app_name: str = "fabric") -> SparkSession:
    from pyspark.sql import SparkSession

    builder = (
        SparkSession.builder.appName(app_name)
        .master(os.environ.get("SPARK_MASTER", "local[*]"))
        .config("spark.driver.memory", os.environ.get("SPARK_DRIVER_MEMORY", "2g"))
        .config("spark.sql.extensions", "io.delta.sql.DeltaSparkSessionExtension")
        .config("spark.sql.catalog.spark_catalog", "org.apache.spark.sql.delta.catalog.DeltaCatalog")
        .config("spark.sql.session.timeZone", "UTC")
    )
    for key, value in s3_conf().items():
        builder = builder.config(key, value)
    return builder.getOrCreate()


def clear_cache() -> None:
    from pyspark.sql import SparkSession

    session = SparkSession.getActiveSession()
    if session is not None:
        session.catalog.clearCache()
