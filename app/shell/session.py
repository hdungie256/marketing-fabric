from typing import Any

import streamlit as st

_ROLE = "_shell_role"
_LOGGED_IN = "_shell_logged_in"
_CURRENT_PAGE = "_shell_current_page"
_REDIRECT = "_shell_redirect"
_REDIRECT_PARAMS = "_shell_redirect_params"
_TOAST = "_shell_toast"
_FILTERS = "_shell_filters"


def role() -> str | None:
    return st.session_state.get(_ROLE)


def set_role(code: str) -> None:
    st.session_state[_ROLE] = code


def logged_in() -> bool:
    return bool(st.session_state.get(_LOGGED_IN))


def sign_in(code: str) -> None:
    set_role(code)
    st.session_state[_LOGGED_IN] = True


def current_page() -> str | None:
    return st.session_state.get(_CURRENT_PAGE)


def set_current_page(key: str) -> None:
    st.session_state[_CURRENT_PAGE] = key


def request_redirect(key: str, query_params: dict[str, str] | None = None) -> None:
    st.session_state[_REDIRECT] = key
    st.session_state[_REDIRECT_PARAMS] = query_params  # only what the caller asks for, never the current page's


def pop_redirect() -> str | None:
    return st.session_state.pop(_REDIRECT, None)


def pop_redirect_params() -> dict[str, str] | None:
    return st.session_state.pop(_REDIRECT_PARAMS, None)


def request_toast(message: str) -> None:
    st.session_state[_TOAST] = message


def pop_toast() -> str | None:
    return st.session_state.pop(_TOAST, None)


def filters(page_key: str) -> dict[str, Any]:
    return st.session_state.setdefault(_FILTERS, {}).setdefault(page_key, {})
