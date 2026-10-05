"""Skeleton placeholders.

Usage: slot = st.empty(); with slot.container(): skeleton("card", 4);
when data arrives: with slot.container(): ...real content...
"""

import streamlit as st

KINDS = ("card", "table", "chart")


def skeleton(kind: str, n: int = 1) -> None:
    if kind not in KINDS:
        raise ValueError(f"kind must be one of {KINDS}, got {kind!r}")
    for column in st.columns(n):
        with column:
            st.html(f'<div class="skeleton skeleton-{kind}" aria-hidden="true"></div>')
