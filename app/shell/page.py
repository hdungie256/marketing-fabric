import streamlit as st
from streamlit.delta_generator import DeltaGenerator

_FOOTNOTES = "_shell_footnotes"


def add_footnote(text: str) -> None:
    notes = st.session_state.setdefault(_FOOTNOTES, [])
    if text not in notes:
        notes.append(text)


def footnotes() -> list[str]:
    return list(st.session_state.get(_FOOTNOTES, []))


def reset_footnotes() -> None:
    st.session_state[_FOOTNOTES] = []


def banner_slot() -> DeltaGenerator:
    raise NotImplementedError("Story 1.11")
