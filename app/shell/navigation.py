from collections.abc import Sequence

import streamlit as st
from streamlit.navigation.page import StreamlitPage

from app.shell import session
from app.shell.registry import GROUPS, PageSpec

FALLBACK_KEY = "no_pages"


def pages_for(role: str, pages: Sequence[PageSpec]) -> list[PageSpec]:
    return [p for p in pages if role in p.roles]


def can_open(role: str | None, key: str, pages: Sequence[PageSpec] | None = None) -> bool:
    """Same rule the runner uses: a redirect only lands on pages in the role's navigation."""
    from app.shell.registry import load_pages

    return any(p.key == key for p in pages_for(role, load_pages() if pages is None else pages))


def home_for(role: str, pages: Sequence[PageSpec]) -> PageSpec | None:
    permitted = pages_for(role, pages)
    return next((p for p in permitted if role in p.home_for), permitted[0] if permitted else None)


def resolve_after_switch(current_key: str | None, new_role: str, pages: Sequence[PageSpec]) -> str:
    if current_key in {p.key for p in pages_for(new_role, pages)}:
        return current_key
    home = home_for(new_role, pages)
    return home.key if home else FALLBACK_KEY


def grouped(role: str, pages: Sequence[PageSpec]) -> dict[str, list[PageSpec]]:
    permitted = pages_for(role, pages)
    groups = {group: [p for p in permitted if p.group == group] for group in GROUPS}
    return {group: specs for group, specs in groups.items() if specs}


def _no_pages() -> None:
    session.set_current_page(FALLBACK_KEY)
    st.title("No pages available")
    st.markdown("No pages available for this role yet.")


def build_navigation(
    role: str, pages: Sequence[PageSpec], current: str | None = None
) -> tuple[StreamlitPage, dict[str, StreamlitPage]]:
    from app.shell.page import wrap

    home = home_for(role, pages)
    if home is None:
        fallback = st.Page(_no_pages, title="No pages available", url_path=FALLBACK_KEY, default=True)
        return st.navigation([fallback], position="hidden"), {}
    default_key = current if current in {p.key for p in pages_for(role, pages)} else home.key
    st_pages = {
        p.key: st.Page(wrap(p), title=p.title, url_path=p.key, icon=p.icon, default=p.key == default_key)
        for p in pages_for(role, pages)
    }
    sections = {group: [st_pages[p.key] for p in specs] for group, specs in grouped(role, pages).items()}
    return st.navigation(sections, position="hidden"), st_pages
