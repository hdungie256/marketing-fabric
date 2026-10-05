import streamlit as st

from app.shell import auth, session
from app.shell.components.feedback import banner_error


def render() -> None:
    st.title("Marketing Data Fabric")
    st.caption("CO5173 · Academic demo")
    missing = auth.missing_env()
    if missing:
        banner_error("Demo login is not configured", cause="Missing environment variable: " + ", ".join(missing))
        return
    with st.form("login"):
        code = st.text_input("Role code", key="_login_code")
        password = st.text_input("Password", type="password", key="_login_password")
        submitted = st.form_submit_button("Sign in", type="primary")
    if submitted:
        if auth.verify(code, password):
            session.sign_in(auth.normalize(code))
            st.rerun()
        st.error("Invalid demo credentials", icon=":material/error:")
