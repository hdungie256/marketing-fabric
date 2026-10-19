from collections.abc import Sequence

import streamlit as st
from streamlit.navigation.page import StreamlitPage

from app.shell import session
from app.shell.navigation import grouped, resolve_after_switch
from app.shell.registry import PageSpec
from app.shell.roles import ROLES


def _on_switch(pages: Sequence[PageSpec]) -> None:
    new_role = st.session_state["_role_switcher"]
    session.set_role(new_role)
    target = resolve_after_switch(session.current_page(), new_role, pages)
    if target != session.current_page():
        session.request_redirect(target)
    session.request_toast(f"Switched to {ROLES[new_role].label}")


def render(pages: Sequence[PageSpec], st_pages: dict[str, StreamlitPage]) -> None:
    role = session.role()
    codes = list(ROLES)
    with st.sidebar:
        st.markdown("**Marketing Data Fabric**")
        st.caption("CO5173 · Academic demo")
        st.selectbox(
            "Role (demo mode)",
            codes,
            index=codes.index(role),
            key="_role_switcher",
            format_func=lambda code: ROLES[code].label,
            on_change=_on_switch,
            args=(pages,),
        )
        st.caption(f"Signed in as {role} · nav filtered to this role")
        with st.container(key="alert-indicator"):
            from app.pages.ops.alerts import alert_indicator

            alert_indicator(role, st_pages)
        for group, specs in grouped(role, pages).items():
            st.caption(group)
            for spec in specs:
                st.page_link(st_pages[spec.key], label=spec.title, icon=spec.icon)
