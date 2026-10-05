import streamlit as st

TOAST_ICONS = {
    "success": ":material/check_circle:",
    "info": ":material/info:",
    "warning": ":material/warning:",
    "error": ":material/error:",
}


def banner_error(message: str, cause: str | None = None) -> None:
    body = f"**{message}**"
    if cause:
        safe = cause.replace("`", "'")
        body += f"\n\n`{safe}`"
    st.error(body, icon=":material/error:")


def denied_block() -> None:
    st.markdown(":gray[:material/lock: *not permitted for role*]")


def toast(message: str, status: str) -> None:
    if status not in TOAST_ICONS:
        raise ValueError(f"status must be one of {sorted(TOAST_ICONS)}, got {status!r}")
    st.toast(message, icon=TOAST_ICONS[status])
