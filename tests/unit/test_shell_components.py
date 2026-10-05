import pytest
from streamlit.testing.v1 import AppTest


def _chip_script(variant):
    from app.shell import status_chip

    status_chip(variant, "Label")


@pytest.mark.parametrize(
    "variant,expected",
    [
        ("success", ":green-badge[:material/check_circle: Label]"),
        ("warning", ":orange-badge[:material/warning: Label]"),
        ("danger", ":red-badge[:material/error: Label]"),
        ("info", ":blue-badge[:material/info: Label]"),
        ("neutral", ":gray-badge[:material/radio_button_unchecked: Label]"),
    ],
)
def test_status_chip_has_icon_and_text(variant, expected):
    at = AppTest.from_function(_chip_script, args=(variant,)).run()
    assert [m.value for m in at.markdown] == [expected]


def test_status_chip_rejects_unknown_variant():
    at = AppTest.from_function(_chip_script, args=("pink",)).run()
    assert "variant must be one of" in at.exception[0].message


def _empty_script():
    from app.shell import empty_state

    empty_state(
        "No attributed orders for CMP-03 in this period.",
        hint="Clear the Campaign filter to see all.",
    )


def test_empty_state_shows_message_and_hint():
    at = AppTest.from_function(_empty_script).run()
    assert ":material/info: No attributed orders for CMP-03 in this period." in [m.value for m in at.markdown]
    assert "Clear the Campaign filter to see all." in [c.value for c in at.caption]


def _banner_script(cause):
    from app.shell import banner_error

    banner_error("Could not load this page", cause=cause)


def test_banner_error_shows_message_and_cause():
    at = AppTest.from_function(_banner_script, args=("FileNotFoundError: `x`",)).run()
    assert at.error[0].value == "**Could not load this page**\n\n`FileNotFoundError: 'x'`"
    assert at.error[0].icon == ":material/error:"


def test_banner_error_without_cause():
    at = AppTest.from_function(_banner_script, args=(None,)).run()
    assert at.error[0].value == "**Could not load this page**"


def _denied_script():
    from app.shell import denied_block

    denied_block()


def test_denied_block_is_muted_not_red():
    at = AppTest.from_function(_denied_script).run()
    assert [m.value for m in at.markdown] == [":gray[:material/lock: *not permitted for role*]"]
    assert not at.error


def _toast_script(status):
    from app.shell import toast

    toast("Change saved", status)


@pytest.mark.parametrize(
    "status,icon",
    [
        ("success", ":material/check_circle:"),
        ("info", ":material/info:"),
        ("warning", ":material/warning:"),
        ("error", ":material/error:"),
    ],
)
def test_toast_uses_status_icon(status, icon):
    at = AppTest.from_function(_toast_script, args=(status,)).run()
    assert at.toast[0].value == "Change saved"
    assert at.toast[0].icon == icon


def test_toast_rejects_unknown_status():
    at = AppTest.from_function(_toast_script, args=("party",)).run()
    assert "status must be one of" in at.exception[0].message
