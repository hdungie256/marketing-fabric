import streamlit as st


def banner_error(message: str, cause: str | None = None) -> None:
    st.error(message if cause is None else f"{message}\n\n{cause}", icon=":material/error:")


def denied_block() -> None:
    st.caption(":material/lock: not permitted for role")


def toast(message: str, status: str) -> None:
    raise NotImplementedError("Story 1.12")
