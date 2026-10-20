"""Spend edit calls to the fabric API (Story 8.5). Standard library only; the API is the only judge of a valid value."""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from datetime import date
from decimal import Decimal

EVENT_KEY = "spend_edit_event"


class SpendServiceUnavailable(Exception):
    pass


def put_spend(campaign_id: str, day: date, value: Decimal, role: str, timeout: float = 30) -> tuple[int, dict]:
    url = f"{os.environ['API_URL']}/spend/campaign_spend/{campaign_id}/{day.isoformat()}"
    body = json.dumps({"allocated_online_spend": str(value)}).encode()
    headers = {"Content-Type": "application/json", "X-Fabric-Role": role}
    request = urllib.request.Request(url, body, headers, method="PUT")
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return response.status, json.loads(response.read())
    except urllib.error.HTTPError as e:
        try:
            payload = json.loads(e.read())
        except ValueError:
            payload = {"detail": {"reason": e.reason}}
        return e.code, payload
    except (urllib.error.URLError, TimeoutError) as e:
        raise SpendServiceUnavailable(str(getattr(e, "reason", e))) from e


def field_errors(status: int, body: dict) -> dict[str, str]:
    detail = body.get("detail")
    if status != 422 or not isinstance(detail, dict) or "field" not in detail:
        return {}  # FastAPI's own 422 (bad body shape) carries a list, not our {field, reason}
    return {detail["field"]: detail["reason"]}
