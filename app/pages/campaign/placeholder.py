from collections.abc import Callable

import streamlit as st

from app.shell import skeleton


def placeholder(story: str) -> Callable[[], None]:
    def render() -> None:
        skeleton("card", 4)
        skeleton("table")
        st.caption(f"Placeholder — implemented in Story {story}")

    return render
