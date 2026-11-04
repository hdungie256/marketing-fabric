from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Any

import streamlit as st

from app.shell import session

KINDS = ("select", "number")


@dataclass(frozen=True)
class Filter:
    """`kind="select"` picks one of `options`; `kind="number"` is a whole number ≥ 0 (`options` unused)."""

    name: str
    label: str
    options: Sequence[Any]
    default: Any = None
    format_func: Callable[[Any], str] = str
    kind: str = "select"


def filter_bar(page_key: str, filters: Sequence[Filter]) -> dict[str, Any]:
    state = session.filters(page_key)
    values: dict[str, Any] = {}
    for column, f in zip(st.columns(len(filters)), filters, strict=True):
        if f.kind not in KINDS:
            raise ValueError(f"{f.name}: kind must be one of {KINDS}, got {f.kind!r}")
        current = state.get(f.name, f.default)
        key = f"_filter_{page_key}_{f.name}"
        with column:
            if f.kind == "number":
                start = current if isinstance(current, int) and current >= 0 else 0
                values[f.name] = int(st.number_input(f.label, min_value=0, value=start, step=1, key=key))
            else:
                options = list(f.options)
                index = options.index(current) if current in options else 0
                values[f.name] = st.selectbox(f.label, options, index=index, key=key, format_func=f.format_func)
        state[f.name] = values[f.name]
    return values
