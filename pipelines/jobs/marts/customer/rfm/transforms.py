from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from pyspark.sql import Column, DataFrame

SEGMENT_ORDER = [
    "Champions",
    "Can't Lose",
    "At Risk",
    "Loyal",
    "Potential Loyalist",
    "Recent First Buyers",
    "Needs Attention",
    "Hibernating",
    "Lost",
]


def quintile(df: DataFrame, order: list[Column], score_col: str) -> DataFrame:
    """Score 5 for the top quintile down to 1. `order` must be total (ties broken)."""
    from pyspark.sql import Window
    from pyspark.sql import functions as F

    window = Window.orderBy(*order)
    return (
        df.withColumn("_bucket", F.ntile(5).over(window))
        .withColumn(score_col, (F.lit(6) - F.col("_bucket")).cast("int"))
        .drop("_bucket")
    )


def condition(r: Column, f: Column, m: Column, spec: dict[str, Any]) -> Column:
    """Build one segment predicate from a rule-table entry.

    Keys: <dim>_min/_max/_eq with dim in r/f/m, <dim>_in lists, and
    `any: [...]` for OR groups. `{}` matches everything.
    """
    from pyspark.sql import functions as F

    cols = {"r": r, "f": f, "m": m}
    parts: list[Column] = []
    for key, value in spec.items():
        if key == "any":
            parts.append(_any(cols, value))
            continue
        dim, _, op = key.partition("_")
        column = cols[dim]
        if op == "min":
            parts.append(column >= value)
        elif op == "max":
            parts.append(column <= value)
        elif op == "eq":
            parts.append(column == value)
        elif op == "in":
            parts.append(column.isin(*value))
        else:  # pragma: no cover - validated by tests
            raise ValueError(f"unknown rule operator {key!r}")
    result: Column = F.lit(True)
    for part in parts:
        result = result & part
    return result


def _any(cols: dict[str, Column], options: list[dict[str, Any]]) -> Column:
    from pyspark.sql import functions as F

    result: Column = F.lit(False)
    for option in options:
        result = result | condition(cols["r"], cols["f"], cols["m"], option)
    return result


def assign_segment(df: DataFrame, rules: list[dict[str, Any]]) -> DataFrame:
    """First-match-wins segment assignment from the ordered rule table."""
    from pyspark.sql import functions as F

    names = [rule["name"] for rule in rules]
    if names != SEGMENT_ORDER:
        raise ValueError(f"rule table order {names} != code order {SEGMENT_ORDER}")
    segment: Column = F.lit(rules[-1]["name"])
    for rule in reversed(rules[:-1]):
        segment = F.when(
            condition(F.col("recency_score"), F.col("frequency_score"), F.col("monetary_score"), rule["when"]),
            F.lit(rule["name"]),
        ).otherwise(segment)
    return df.withColumn("segment", segment)


def build_rfm(
    orders: DataFrame,
    customers: DataFrame,
    lines: DataFrame,
    as_of: str,
    segment_rules: list[dict[str, Any]],
) -> DataFrame:
    """RFM mart at grain customer (FR-32, R5, R18).

    Recency in days to as-of, frequency counts technical orders (R1),
    monetary sums gross_value ex shipping (R2/R3). Only buying customers
    appear; CRM attributes join left so an order never disappears.
    Categories are a sorted comma-joined string (no array types in OM/PG).
    """
    from pyspark.sql import functions as F

    per_customer = (
        orders.groupBy("customer_id").agg(
            F.max("order_date").alias("last_order_date"),
            F.countDistinct("order_key").cast("int").alias("frequency_orders"),
            F.sum("gross_value").alias("monetary_value"),
        )
    ).withColumn("recency_days", F.datediff(F.lit(as_of).cast("date"), F.col("last_order_date")))
    scored = quintile(per_customer, [F.col("recency_days").asc(), F.col("customer_id").asc()], "recency_score")
    scored = quintile(scored, [F.col("frequency_orders").desc(), F.col("customer_id").asc()], "frequency_score")
    scored = quintile(scored, [F.col("monetary_value").desc(), F.col("customer_id").asc()], "monetary_score")
    categories = lines.groupBy("customer_id").agg(
        F.concat_ws(",", F.sort_array(F.collect_set("canonical_category"))).alias("categories")
    )
    profile = customers.select("customer_id", "gender", "location", "tenure_months")
    out = (
        scored.join(categories, "customer_id", "left")
        .join(profile, "customer_id", "left")
        .withColumn("categories", F.coalesce(F.col("categories"), F.lit("")))
        .withColumn("provenance", F.lit("original"))
    )
    return assign_segment(out, segment_rules).select(
        "customer_id",
        "recency_days",
        "recency_score",
        "frequency_orders",
        "frequency_score",
        "monetary_value",
        "monetary_score",
        "segment",
        "categories",
        "gender",
        "location",
        "tenure_months",
        "provenance",
    )
