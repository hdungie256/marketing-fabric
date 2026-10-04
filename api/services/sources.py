from typing import Any

from api.repositories import sources

TABLES = {
    "campaign": ("campaigns", "targets", "attribution"),
    "promotion": ("coupon_plan",),
    "spend": ("campaign_spend",),
}


class UnknownTable(Exception):
    pass


def read_table(source: str, table: str) -> dict[str, Any]:
    if table not in TABLES.get(source, ()):
        raise UnknownTable(f"{source}/{table}")
    return {
        "source": source,
        "table": table,
        "source_version": sources.source_version(source),
        "items": sources.fetch_table(source, table),
    }
