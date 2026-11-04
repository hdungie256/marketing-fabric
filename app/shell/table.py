import hashlib
from collections.abc import Callable
from typing import Any

import pandas as pd
import streamlit as st

import fabric_control
from app.shell import session
from app.shell.components.definition_dialog import definition_dialog
from app.shell.format import FORMATTERS

LOCK = "🔒"
DENIED_TEXT = f"{LOCK} not permitted for role"
DENIED_SUFFIX = "__denied"
ACCENT_TINT = "#E8EEFE"  # DESIGN.md colors.accent-tint


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
    info_terms: dict[str, str] | None = None,
    highlight: Callable[[pd.Series], bool] | None = None,
    widths: dict[str, str] | None = None,
) -> None:
    """`widths` caps a column ("small" | "medium" | "large") so a long text column does not push the
    last columns off screen."""
    masked = _cached_masked_columns(session.role(), dataset_id) if dataset_id else frozenset()
    out, formatters, config = prepare_table(df, masked, campaign_col, formats)
    for column, width in (widths or {}).items():
        if column in out.columns:
            config[column] = {**config.get(column, {}), "width": width}
    styler = out.style.format(formatters)
    if highlight:
        styler = styler.apply(
            lambda row: [f"background-color: {ACCENT_TINT}" if highlight(row) else ""] * len(row), axis=1
        )
    st.dataframe(styler, column_config=config, hide_index=True, width="stretch")
    infos = [(column, term_id) for column, term_id in (info_terms or {}).items() if column in out.columns]
    if infos:
        with st.container(
            key=f"table-info-row-{hashlib.md5('|'.join(c for c, _ in infos).encode()).hexdigest()[:8]}",
            horizontal=True,
            gap="small",
        ):
            for column, term_id in infos:
                if st.button(f"ⓘ {column}", key=f"table-info-{column}", width="content"):
                    definition_dialog(term_id)
