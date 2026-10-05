import logging
import time
from collections.abc import Callable

import streamlit as st
from streamlit.delta_generator import DeltaGenerator

import fabric_control
from app.shell import session
from app.shell.components.feedback import banner_error, denied_block
from app.shell.errors import NotPermittedError
from app.shell.registry import PageSpec
from app.shell.roles import ROLES

log = logging.getLogger("app.shell")

_FOOTNOTES = "_shell_footnotes"
_BANNER = "_shell_banner_slot"


def add_footnote(text: str) -> None:
    notes = st.session_state.setdefault(_FOOTNOTES, [])
    if text not in notes:
        notes.append(text)


def footnotes() -> list[str]:
    return list(st.session_state.get(_FOOTNOTES, []))


def reset_footnotes() -> None:
    st.session_state[_FOOTNOTES] = []


def banner_slot() -> DeltaGenerator:
    return st.session_state[_BANNER]


def _header(title: str) -> None:
    left, right = st.columns([3, 1], vertical_alignment="bottom")
    left.title(title)
    with right.container(key="viewing-as"):
        st.markdown(f"Viewing as: {ROLES[session.role()].label}")


def _footnote_strip() -> None:
    notes = footnotes()
    if notes:
        with st.container(key="footnote-strip"):
            for note in notes:
                st.caption(note)


def _record(page: str, ms: float) -> None:
    try:
        fabric_control.record_timing(page, ms)
    except Exception as e:  # telemetry must never break a page
        log.warning("record_timing failed for %s: %s", page, e)


def wrap(spec: PageSpec) -> Callable[[], None]:
    def page() -> None:
        started = time.perf_counter()
        session.set_current_page(spec.key)
        reset_footnotes()
        try:
            _header(spec.title)
            st.session_state[_BANNER] = st.container()
            try:
                spec.render()
            except NotPermittedError:
                denied_block()
            except Exception as e:
                log.exception("page %s failed", spec.key)
                banner_error("Could not load this page", cause=f"{type(e).__name__}: {e}")
            _footnote_strip()
        finally:
            _record(spec.key, (time.perf_counter() - started) * 1000)

    page.__name__ = spec.key
    return page
