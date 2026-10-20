import uuid
from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Any

import fabric_control as fc
from api.repositories import spend

SOURCE = "spend"
DATASET = "raw/spend/campaign_spend"
VALUE = "allocated_online_spend"


class Forbidden(Exception):
    pass


class Invalid(Exception):
    def __init__(self, field: str, reason: str):
        super().__init__(reason)
        self.field = field
        self.reason = reason


class RefreshNotStarted(Exception):
    def __init__(self, event: dict[str, Any], reason: str):
        super().__init__(reason)
        self.event = event


def change_event(campaign_id: str, day: date, version: int) -> dict[str, Any]:
    return {
        "event_id": uuid.uuid4().hex,
        "emitted_at": datetime.now(UTC).isoformat(),
        "source": DATASET,
        "keys": {"campaign_id": campaign_id, "date": day.isoformat()},
        "source_version": version,
    }


def save(campaign_id: str, day: date, value: Decimal) -> int:
    if value < 0:
        raise Invalid(VALUE, "must be 0 or more")
    online = spend.online_spend(day)
    with spend.connect() as conn, conn.transaction():
        spend.lock_source(conn, SOURCE)
        period = spend.campaign_period(conn, campaign_id)
        if period is None:
            raise Invalid("campaign_id", f"unknown campaign {campaign_id}")
        start, end = period
        if not start <= day <= end:
            raise Invalid("date", f"{day} is outside the {campaign_id} period {start} to {end}")
        if online is None:
            raise Invalid("date", f"no online spend recorded for {day}")
        if value > online:
            raise Invalid(VALUE, f"{value} is above that day's online spend {online}")
        total = value + spend.other_allocations(conn, campaign_id, day)
        if total > online:
            raise Invalid(VALUE, f"allocations on {day} would total {total}, above that day's online spend {online}")
        if not spend.update_allocation(conn, campaign_id, day, value):
            raise Invalid("date", f"{campaign_id} has no spend row on {day}")
        return spend.bump_version(conn, SOURCE)


def edit_allocation(role: str, campaign_id: str, day: date, value: Decimal) -> dict[str, Any]:
    allowed, reason = fc.can_edit(DATASET, role)
    if not allowed:
        raise Forbidden(reason)
    event = change_event(campaign_id, day, save(campaign_id, day, value))
    try:
        dag_run_id = fc.trigger("partial_refresh", event)
    except Exception as e:
        fc.record_event(event, None)
        raise RefreshNotStarted(event, f"change saved but partial refresh did not start: {e}") from e
    fc.record_event(event, dag_run_id)
    return {"event": event, "dag_run_id": dag_run_id}
