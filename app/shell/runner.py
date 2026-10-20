import streamlit as st

from app.shell import login, session, sidebar
from app.shell.components.feedback import banner_error
from app.shell.navigation import build_navigation
from app.shell.registry import RegistryError, load_pages, validate
from app.shell.theme import inject_css


def run() -> None:
    inject_css()
    if not session.logged_in():
        login.render()
        return
    pages = load_pages()
    try:
        validate(pages)
    except RegistryError as e:
        banner_error("Page registry is invalid", cause=str(e))
        st.stop()
    nav, st_pages = build_navigation(session.role(), pages, session.current_page())
    sidebar.render(pages, st_pages)
    target, params = session.pop_redirect(), session.pop_redirect_params()
    if target in st_pages:
        st.switch_page(st_pages[target], query_params=params)
    message = session.pop_toast()
    if message:
        st.toast(message, icon=":material/swap_horiz:")
    nav.run()
