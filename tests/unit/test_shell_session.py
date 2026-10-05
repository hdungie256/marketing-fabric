from streamlit.testing.v1 import AppTest


def _session_script():
    import streamlit as st

    from app.shell import session

    if not session.logged_in():
        session.sign_in("UG03")
        session.set_current_page("targets")
        session.request_redirect("campaign_overview")
        session.request_toast("Switched")
    st.text(f"{session.role()}|{session.current_page()}|{session.pop_redirect()}|{session.pop_toast()}")


def test_session_values_and_one_shot_requests():
    at = AppTest.from_function(_session_script).run()
    assert at.text[0].value == "UG03|targets|campaign_overview|Switched"
    at.run()
    assert at.text[0].value == "UG03|targets|None|None"


def _filter_script():
    import streamlit as st

    from app.shell import Filter, filter_bar

    if st.session_state.get("show", True):
        values = filter_bar("overview", [Filter("campaign", "Campaign", ["All", "CMP-01", "CMP-02"])])
        st.text(values["campaign"])


def test_filter_defaults_to_first_option():
    at = AppTest.from_function(_filter_script).run()
    assert at.text[0].value == "All"


def test_filter_value_survives_when_widget_is_not_rendered():
    at = AppTest.from_function(_filter_script).run()
    at.selectbox(key="_filter_overview_campaign").set_value("CMP-02").run()
    at.session_state["show"] = False
    at.run()
    at.session_state["show"] = True
    at.run()
    assert at.selectbox(key="_filter_overview_campaign").value == "CMP-02"
    assert at.text[0].value == "CMP-02"
