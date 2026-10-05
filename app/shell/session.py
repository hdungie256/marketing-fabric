import streamlit as st

_ROLE = "_shell_role"


def role() -> str | None:
    return st.session_state.get(_ROLE)


def set_role(code: str) -> None:
    st.session_state[_ROLE] = code
