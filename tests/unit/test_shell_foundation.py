import tomllib
from pathlib import Path

from streamlit.testing.v1 import AppTest

import app.shell as shell
from app.shell import theme
from app.shell.errors import NotPermittedError, UnknownTermError

ROOT = Path(__file__).resolve().parents[2]

PUBLIC_API = {
    "CAMPAIGN_COLORS",
    "DataSource",
    "Filter",
    "NOTE_TEXT",
    "NotPermittedError",
    "PageSpec",
    "SERIES_NEUTRAL",
    "STATUS_COLORS",
    "UnknownTermError",
    "add_footnote",
    "banner_error",
    "banner_slot",
    "current_source",
    "denied_block",
    "empty_state",
    "filter_bar",
    "fmt_count",
    "fmt_date",
    "fmt_money",
    "fmt_pct",
    "fmt_ratio",
    "fmt_time",
    "footnotes",
    "metric",
    "run",
    "skeleton",
    "status_chip",
    "table",
    "toast",
}


def test_public_api_is_complete():
    assert set(shell.__all__) == PUBLIC_API
    for name in PUBLIC_API:
        assert hasattr(shell, name), name


def test_config_toml_matches_design_tokens():
    cfg = tomllib.loads((ROOT / ".streamlit" / "config.toml").read_text())["theme"]
    assert cfg["base"] == "light"
    assert cfg["primaryColor"] == "#2F5BEA"
    assert cfg["backgroundColor"] == "#F6F7F9"
    assert cfg["textColor"] == "#1A1F29"
    assert cfg["baseFontSize"] == 16
    assert cfg["chartCategoricalColors"] == list(theme.CAMPAIGN_COLORS.values())
    assert len(cfg["chartSequentialColors"]) == 10
    assert cfg["chartSequentialColors"][0] == "#E8EEFE"
    assert cfg["chartSequentialColors"][-1] == "#1F3FAE"
    assert cfg["greenColor"] == theme.STATUS_COLORS["success"]
    assert cfg["orangeColor"] == theme.STATUS_COLORS["warning"]
    assert cfg["redColor"] == theme.STATUS_COLORS["danger"]
    assert cfg["grayColor"] == theme.STATUS_COLORS["muted"]
    assert cfg["sidebar"]["backgroundColor"] == "#FBFBFC"


def test_campaign_colors_are_fixed_by_slot():
    assert theme.CAMPAIGN_COLORS == {
        "CMP-01": "#2a78d6",
        "CMP-02": "#d95926",
        "CMP-03": "#1baf7a",
        "CMP-04": "#4a3aa7",
        "CMP-05": "#eda100",
    }
    assert theme.SERIES_NEUTRAL == "#848B97"


def test_css_joins_every_styles_file_in_name_order(tmp_path, monkeypatch):
    (tmp_path / "b.css").write_text("b{}")
    (tmp_path / "a.css").write_text("a{}")
    monkeypatch.setattr(theme, "STYLES_DIR", tmp_path)
    assert theme.css() == "a{}\nb{}"


def _footnote_script():
    import streamlit as st

    from app.shell.page import add_footnote, footnotes, reset_footnotes

    reset_footnotes()
    add_footnote("a")
    add_footnote("b")
    add_footnote("a")
    st.text("|".join(footnotes()))


def test_footnotes_are_deduplicated_in_order():
    at = AppTest.from_function(_footnote_script).run()
    assert not at.exception
    assert at.text[0].value == "a|b"


def test_errors_carry_their_ids():
    assert UnknownTermError("attributed_orders").term_id == "attributed_orders"
    assert "attributed_orders" in str(UnknownTermError("attributed_orders"))
    assert NotPermittedError("mart_finance/sku_cost").dataset_id == "mart_finance/sku_cost"
    assert "not permitted" in str(NotPermittedError("mart_finance/sku_cost")).lower()
