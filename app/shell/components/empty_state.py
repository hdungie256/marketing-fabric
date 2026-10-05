import streamlit as st


def empty_state(message: str, hint: str | None = None) -> None:
    with st.container(border=True):
        st.markdown(f":material/info: {message}")
        if hint:
            st.caption(hint)
