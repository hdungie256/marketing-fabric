from collections.abc import Callable
from typing import Any

import pandas as pd
import streamlit as st

import fabric_control
from app.shell import session
from app.shell.format import FORMATTERS

LOCK = "🔒"
DENIED_TEXT = f"{LOCK} not permitted for role"
DENIED_SUFFIX = "__denied"


def masked_columns(role: str, dataset_id: str) -> frozenset[str]:
    return frozenset(
        row["column"]
        for row in fabric_control.effective_matrix()
        if row.get("role") == role
        and row.get("dataset_id") == dataset_id
        and str(row.get("action", "")).startswith("mask")
    )


_cached_masked_columns = st.cache_data(ttl=60, show_spinner=False)(masked_columns)


def _is_missing(value: Any) -> bool:
    return value is None or (pd.api.types.is_scalar(value) and bool(pd.isna(value)))


def _formatter(fmt: Callable[[Any], str]) -> Callable[[Any], str]:
    return lambda value: value if isinstance(value, str) else fmt(value)


def _visible(column: str) -> bool:
    return not column.startswith("_") and not column.endswith(DENIED_SUFFIX)


def prepare_table(
    df: pd.DataFrame,
    masked_cols: frozenset[str] = frozenset(),
    campaign_col: str | None = None,
    formats: dict[str, str] | None = None,
) -> tuple[pd.DataFrame, dict[str, Callable[[Any], str]], dict[str, dict]]:
    out = df.copy()
    kinds: dict[str, str] = {}
    for column in out.columns:
        if not _visible(column) or column in masked_cols:
            continue
        if formats and column in formats:
            kinds[column] = formats[column]
        elif pd.api.types.is_integer_dtype(out[column]):
            kinds[column] = "count"
        elif pd.api.types.is_float_dtype(out[column]):
            kinds[column] = "money"
    for column, kind in kinds.items():
        if kind not in FORMATTERS:
            raise ValueError(f"{column}: unknown format {kind!r}; use one of {sorted(FORMATTERS)}")

    for flag in [c for c in out.columns if c.endswith(DENIED_SUFFIX)]:
        column = flag.removesuffix(DENIED_SUFFIX)
        if column in out.columns:
            denied = out[flag].fillna(False).astype(bool)
            if denied.any():
                out[column] = out[column].astype(object)
                out.loc[denied, column] = DENIED_TEXT
    for column in masked_cols & set(out.columns):
        values = [v if _is_missing(v) or v == DENIED_TEXT else f"{LOCK} {v}" for v in out[column]]
        out[column] = pd.Series(values, index=out.index, dtype=object)
    if campaign_col and "campaign_name" in out.columns:
        out[campaign_col] = out["campaign_name"].astype(str) + " · " + out[campaign_col].astype(str)
        out = out.drop(columns=["campaign_name"])
    out = out[[c for c in out.columns if _visible(c)]]

    formatters = {c: _formatter(FORMATTERS[k]) for c, k in kinds.items() if c in out.columns}
    config = {
        c: st.column_config.NumberColumn(alignment="right")
        if pd.api.types.is_numeric_dtype(out[c])
        else st.column_config.TextColumn(alignment="right")
        for c in formatters
    }
    return out, formatters, config


def table(
    df: pd.DataFrame,
    *,
    dataset_id: str | None = None,
    campaign_col: str | None = None,
    formats: dict[str, str] | None = None,
) -> None:
    masked = _cached_masked_columns(session.role(), dataset_id) if dataset_id else frozenset()
    out, formatters, config = prepare_table(df, masked, campaign_col, formats)
    st.dataframe(out.style.format(formatters), column_config=config, hide_index=True, width="stretch")
