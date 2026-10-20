import math
from datetime import UTC, date, datetime
from decimal import Decimal

import numpy as np
import pandas as pd
import pytest

from app.shell.format import FORMATTERS, fmt_count, fmt_date, fmt_money, fmt_pct, fmt_ratio, fmt_time


@pytest.mark.parametrize("fn", [fmt_count, fmt_money, fmt_ratio, fmt_pct, fmt_date, fmt_time])
@pytest.mark.parametrize("missing", [None, math.nan])
def test_missing_values_render_as_dash(fn, missing):
    assert fn(missing) == "—"


@pytest.mark.parametrize("value,expected", [(1290, "1,290"), (0, "0"), (-1234, "-1,234"), (1234567.0, "1,234,567")])
def test_fmt_count(value, expected):
    assert fmt_count(value) == expected


@pytest.mark.parametrize(
    "value,expected", [(12345.6, "12,346"), (0.5, "1"), (2.5, "3"), (-1234.5, "-1,235"), (-1234.4, "-1,234")]
)
def test_fmt_money_rounds_half_away_from_zero_without_symbol(value, expected):
    assert fmt_money(value) == expected


def test_fmt_money_with_places_keeps_cents():
    assert fmt_money(Decimal("1356.325"), places=2) == "1,356.33"
    assert fmt_money(0.4, places=2) == "0.40"
    assert fmt_money(None, places=2) == "—"


@pytest.mark.parametrize("value,expected", [(3.4178, "3.42×"), (0, "0.00×"), (1.005, "1.01×"), (1234.5, "1,234.50×")])
def test_fmt_ratio(value, expected):
    assert fmt_ratio(value) == expected


@pytest.mark.parametrize("value,expected", [(0.1234, "12.3%"), (1, "100.0%"), (0.00049, "0.0%"), (-0.05, "-5.0%")])
def test_fmt_pct_takes_a_fraction(value, expected):
    assert fmt_pct(value) == expected


def test_fmt_date_is_iso():
    assert fmt_date(date(2019, 12, 31)) == "2019-12-31"
    assert fmt_date(datetime(2019, 12, 31, 23, 59)) == "2019-12-31"


def test_fmt_time_converts_to_app_timezone(monkeypatch):
    monkeypatch.delenv("APP_TZ", raising=False)
    assert fmt_time(datetime(2026, 10, 5, 7, 5, tzinfo=UTC)) == "14:05"


def test_fmt_time_treats_naive_datetime_as_utc(monkeypatch):
    monkeypatch.setenv("APP_TZ", "UTC")
    assert fmt_time(datetime(2026, 10, 5, 7, 5)) == "07:05"


def test_formatters_cover_metric_kinds():
    assert set(FORMATTERS) == {"count", "money", "ratio", "pct"}


@pytest.mark.parametrize("fn", [fmt_count, fmt_money, fmt_ratio, fmt_pct])
@pytest.mark.parametrize("missing", [pd.NA, math.inf, -math.inf, np.float32("nan"), np.float64("nan")])
def test_pandas_na_and_infinity_render_as_dash(fn, missing):
    assert fn(missing) == "—"


@pytest.mark.parametrize("fn", [fmt_date, fmt_time])
def test_nat_and_na_render_as_dash_for_dates(fn):
    assert fn(pd.NaT) == "—"
    assert fn(pd.NA) == "—"
