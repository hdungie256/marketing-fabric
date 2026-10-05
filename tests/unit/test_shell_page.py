import pytest
from streamlit.testing.v1 import AppTest

import fabric_control


@pytest.fixture
def timings(monkeypatch):
    calls = []
    monkeypatch.setattr(fabric_control, "record_timing", lambda page, ms: calls.append((page, ms)))
    return calls


def _page_script(mode):
    import streamlit as st

    from app.shell import add_footnote, banner_slot, session
    from app.shell.errors import NotPermittedError
    from app.shell.page import wrap
    from app.shell.registry import PageSpec

    def render():
        if mode == "boom":
            raise ValueError("fixture missing")
        if mode == "denied":
            raise NotPermittedError("mart_finance/sku_cost")
        banner_slot().text("banner here")
        add_footnote("Note A")
        add_footnote("Note A")
        st.text("body")

    session.set_role("UG03")
    wrap(PageSpec("targets", "Targets", "Campaigns", render, frozenset({"UG03"})))()
    st.text(f"current={session.current_page()}")


def test_wrap_renders_header_body_and_footnotes(timings):
    at = AppTest.from_function(_page_script, args=("ok",)).run()
    assert not at.exception
    assert at.title[0].value == "Targets"
    assert any("Viewing as: Marketing Manager (UG03)" in m.value for m in at.markdown)
    assert [t.value for t in at.text] == ["banner here", "body", "current=targets"]
    assert [c.value for c in at.caption].count("Note A") == 1


def test_wrap_records_timing_once(timings):
    AppTest.from_function(_page_script, args=("ok",)).run()
    assert len(timings) == 1
    assert timings[0][0] == "targets" and timings[0][1] >= 0


def test_wrap_shows_error_banner_and_still_records_timing(timings):
    at = AppTest.from_function(_page_script, args=("boom",)).run()
    assert not at.exception
    assert "Could not load this page" in at.error[0].value
    assert "fixture missing" in at.error[0].value
    assert len(timings) == 1


def test_wrap_shows_denied_block_on_permission_error(timings):
    at = AppTest.from_function(_page_script, args=("denied",)).run()
    assert not at.error
    # caption before Story 1.12 merges, muted markdown after — both must say why
    assert any("not permitted for role" in e.value for e in [*at.caption, *at.markdown])


def test_timing_failure_does_not_break_page(monkeypatch):
    def fail(page, ms):
        raise NotImplementedError("record_timing")

    monkeypatch.setattr(fabric_control, "record_timing", fail)
    at = AppTest.from_function(_page_script, args=("ok",)).run()
    assert not at.exception
    assert at.title[0].value == "Targets"


def _skeleton_script(kind):
    from app.shell import skeleton

    skeleton(kind, 3)


def test_skeleton_rejects_unknown_kind():
    at = AppTest.from_function(_skeleton_script, args=("spinner",)).run()
    assert "kind must be one of" in at.exception[0].message


def test_skeleton_renders_shapes():
    at = AppTest.from_function(_skeleton_script, args=("card",)).run()
    assert not at.exception
