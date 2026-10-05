from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Any

import streamlit as st

from app.shell import session


@dataclass(frozen=True)
class Filter:
    name: str
    label: str
    options: Sequence[Any]
    default: Any = None
    format_func: Callable[[Any], str] = str


def filter_bar(page_key: str, filters: Sequence[Filter]) -> dict[str, Any]:
    state = session.filters(page_key)
    values: dict[str, Any] = {}
    for column, f in zip(st.columns(len(filters)), filters, strict=True):
        options = list(f.options)
        current = state.get(f.name, f.default)
        index = options.index(current) if current in options else 0
        with column:
            values[f.name] = st.selectbox(
                f.label, options, index=index, key=f"_filter_{page_key}_{f.name}", format_func=f.format_func
            )
        state[f.name] = values[f.name]
    return values
