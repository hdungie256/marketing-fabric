from pathlib import Path

import streamlit as st

CAMPAIGN_COLORS = {
    "CMP-01": "#2a78d6",
    "CMP-02": "#d95926",
    "CMP-03": "#1baf7a",
    "CMP-04": "#4a3aa7",
    "CMP-05": "#eda100",
}
SERIES_NEUTRAL = "#848B97"
STATUS_COLORS = {
    "success": "#146C2E",
    "warning": "#92400E",
    "danger": "#99180C",
    "info": "#2F5BEA",
    "muted": "#5B6472",
}
STYLES_DIR = Path(__file__).parent / "styles"


def css() -> str:
    return "\n".join(path.read_text() for path in sorted(STYLES_DIR.glob("*.css")))


def inject_css() -> None:
    st.html(f"<style>{css()}</style>")
