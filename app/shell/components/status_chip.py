import streamlit as st

CHIPS = {
    "success": ("green", ":material/check_circle:"),
    "warning": ("orange", ":material/warning:"),
    "danger": ("red", ":material/error:"),
    "info": ("blue", ":material/info:"),
    "neutral": ("gray", ":material/radio_button_unchecked:"),
}


def status_chip(variant: str, text: str) -> None:
    if variant not in CHIPS:
        raise ValueError(f"variant must be one of {sorted(CHIPS)}, got {variant!r}")
    color, icon = CHIPS[variant]
    st.badge(text, icon=icon, color=color)
