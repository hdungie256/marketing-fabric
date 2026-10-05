import math
import os
from collections.abc import Callable
from datetime import UTC, datetime
from decimal import ROUND_HALF_UP, Decimal
from typing import Any
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd

DASH = "—"


def _missing(value: Any) -> bool:
    if value is None:
        return True
    if isinstance(value, (float, np.floating)):
        return not math.isfinite(value)
    if not pd.api.types.is_scalar(value):
        return False
    return bool(pd.isna(value))


def _quantize(value: Any, places: str) -> Decimal:
    return Decimal(str(value)).quantize(Decimal(places), rounding=ROUND_HALF_UP)


def app_tz() -> ZoneInfo:
    return ZoneInfo(os.environ.get("APP_TZ", "Asia/Ho_Chi_Minh"))


def fmt_count(value: Any) -> str:
    return DASH if _missing(value) else f"{int(_quantize(value, '1')):,}"


def fmt_money(value: Any) -> str:
    return DASH if _missing(value) else f"{int(_quantize(value, '1')):,}"


def fmt_ratio(value: Any) -> str:
    return DASH if _missing(value) else f"{_quantize(value, '0.01'):,}×"


def fmt_pct(value: Any) -> str:
    return DASH if _missing(value) else f"{_quantize(Decimal(str(value)) * 100, '0.1')}%"


def fmt_date(value: Any) -> str:
    if _missing(value):
        return DASH
    return (value.date() if isinstance(value, datetime) else value).isoformat()


def fmt_time(value: Any) -> str:
    if _missing(value):
        return DASH
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    return value.astimezone(app_tz()).strftime("%H:%M")


FORMATTERS: dict[str, Callable[[Any], str]] = {
    "count": fmt_count,
    "money": fmt_money,
    "ratio": fmt_ratio,
    "pct": fmt_pct,
}
