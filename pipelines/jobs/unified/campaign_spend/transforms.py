from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pyspark.sql import DataFrame

SPEND_COLUMNS = ["campaign_id", "date", "allocated_online_spend", "basis", "provenance", "provenance_note"]
DAILY_COLUMNS = ["date", "online_spend", "offline_spend", "provenance"]
# Finance file dates are US month/day/year, e.g. 1/15/2019; unparseable dates become NULL and fail date_not_null.
DAILY_DATE_FORMAT = "M/d/yyyy"


def campaign_spend(raw: DataFrame) -> DataFrame:
    return raw.withColumnRenamed("date_iso", "date").select(*SPEND_COLUMNS)


def daily_spend(raw: DataFrame) -> DataFrame:
    from pyspark.sql import functions as F

    return raw.withColumn("date", F.to_date("date", DAILY_DATE_FORMAT)).select(*DAILY_COLUMNS)


def days_without_daily_spend(spend: DataFrame, daily: DataFrame) -> DataFrame:
    return spend.join(daily.select("date"), "date", "left_anti")


def days_over_allocated(spend: DataFrame, daily: DataFrame) -> DataFrame:
    """Days where campaign allocations exceed the day's online spend (R8: allocations are a subset)."""
    from pyspark.sql import functions as F

    allocated = spend.groupBy("date").agg(F.sum("allocated_online_spend").alias("allocated"))
    return allocated.join(daily, "date").filter(F.col("allocated") > F.col("online_spend"))


def outside_campaign_dates(spend: DataFrame, campaigns: DataFrame) -> DataFrame:
    from pyspark.sql import functions as F

    window = campaigns.select("campaign_id", "start_date", "end_date")
    return spend.join(window, "campaign_id").filter(~F.col("date").between(F.col("start_date"), F.col("end_date")))
