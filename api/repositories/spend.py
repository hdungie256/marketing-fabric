import csv
import io
import os
from datetime import date, datetime
from decimal import Decimal

import psycopg

DAILY_DATE_FORMAT = "%m/%d/%Y"


def connect():
    return psycopg.connect(os.environ["SOURCES_DB_DSN"])


def online_spend(day: date) -> Decimal | None:
    import boto3

    s3 = boto3.client("s3", endpoint_url=os.environ["S3_ENDPOINT"], region_name="us-east-1")
    body = s3.get_object(Bucket=os.environ.get("SOURCES_BUCKET", "sources"), Key="spend/daily_spend.csv")["Body"]
    for row in csv.DictReader(io.StringIO(body.read().decode())):
        if datetime.strptime(row["date"], DAILY_DATE_FORMAT).date() == day:
            return Decimal(row["online_spend"])
    return None


def lock_source(conn, source: str) -> None:
    conn.execute("SELECT version FROM meta.source_versions WHERE source = %s FOR UPDATE", (source,))


def campaign_period(conn, campaign_id: str) -> tuple[date, date] | None:
    return conn.execute(
        "SELECT start_date, end_date FROM campaign.campaigns WHERE campaign_id = %s", (campaign_id,)
    ).fetchone()


def other_allocations(conn, campaign_id: str, day: date) -> Decimal:
    row = conn.execute(
        """
        SELECT coalesce(sum(allocated_online_spend), 0) FROM spend.campaign_spend
        WHERE date_iso = %s AND campaign_id <> %s
        """,
        (day, campaign_id),
    ).fetchone()
    return row[0]


def update_allocation(conn, campaign_id: str, day: date, value: Decimal) -> bool:
    cursor = conn.execute(
        "UPDATE spend.campaign_spend SET allocated_online_spend = %s WHERE campaign_id = %s AND date_iso = %s",
        (value, campaign_id, day),
    )
    return cursor.rowcount == 1


def bump_version(conn, source: str) -> int:
    return conn.execute(
        "UPDATE meta.source_versions SET version = version + 1 WHERE source = %s RETURNING version", (source,)
    ).fetchone()[0]
