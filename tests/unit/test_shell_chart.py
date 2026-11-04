import pandas as pd
import pytest
from streamlit import dataframe_util
from streamlit.testing.v1 import AppTest

from app.shell.chart import SERIES_COLORS, build_chart
from app.shell.theme import CAMPAIGN_COLORS


def spec(df, **kw):
    return build_chart(df, x="x", y="y", x_title="X", y_title="Y", **kw).to_dict()


def _layers(s):
    return s.get("layer") or [s]


def _encodings(s):
    return [layer.get("encoding", {}) for layer in _layers(s)]


def find_color_scale(s):
    for enc in _encodings(s):
        if "color" in enc and "scale" in enc["color"]:
            return enc["color"]["scale"]
    raise AssertionError("no color scale")


def has_text_layer(s):
    return any(layer.get("mark") == "text" or layer.get("mark", {}).get("type") == "text" for layer in _layers(s))


def axis_titles(s):
    titles = set()
    for enc in _encodings(s):
        for ch in ("x", "y"):
            if ch in enc and "title" in enc[ch]:
                titles.add(enc[ch]["title"])
    return titles


def has_tooltip(s):
    return any("tooltip" in enc for enc in _encodings(s))


def test_campaign_series_use_fixed_colors():
    df = pd.DataFrame({"x": ["a", "b"], "y": [1, 2], "s": ["CMP19_02", "CMP19_05"]})
    scale = find_color_scale(spec(df, series="s"))
    assert scale["domain"] == ["CMP19_02", "CMP19_05"]
    assert scale["range"] == [CAMPAIGN_COLORS["CMP19_02"], CAMPAIGN_COLORS["CMP19_05"]]


def test_non_campaign_series_use_series_palette_in_order():
    df = pd.DataFrame({"x": [1, 1], "y": [1, 2], "s": ["Paid Search", "Email CRM"]})
    assert find_color_scale(spec(df, series="s"))["range"] == SERIES_COLORS[:2]


def test_direct_labels_only_up_to_four_series():
    four = pd.DataFrame({"x": [1] * 4, "y": range(4), "s": list("abcd")})
    five = pd.DataFrame({"x": [1] * 5, "y": range(5), "s": list("abcde")})
    assert has_text_layer(spec(four, series="s"))
    assert not has_text_layer(spec(five, series="s"))


def test_axes_titled_and_tooltip_present():
    s = spec(pd.DataFrame({"x": ["a"], "y": [1]}))
    assert axis_titles(s) == {"X", "Y"} and has_tooltip(s)


def test_unknown_kind_rejected():
    with pytest.raises(ValueError):
        build_chart(pd.DataFrame({"x": [1], "y": [1]}), x="x", y="y", x_title="X", y_title="Y", kind="pie")


def _chart_script():
    import pandas as pd

    from app.shell.chart import chart

    df = pd.DataFrame({"x": ["a", "b"], "y": [1, 2]})
    chart(df, key="t", title="T", x="x", y="y", x_title="X", y_title="Y")


def test_table_view_toggle_renders_dataframe():
    at = AppTest.from_function(_chart_script).run()
    assert not at.exception
    assert len(at.dataframe) == 0
    at.toggle(key="t_table_view").set_value(True).run()
    assert not at.exception
    assert len(at.dataframe) == 1


def _share_chart_script():
    import pandas as pd

    from app.shell.chart import chart

    df = pd.DataFrame({"segment": ["Champions"], "customers": [299], "share": [299 / 1468]})
    chart(df, key="t", title="T", x="segment", y="customers", x_title="X", y_title="Y", table_formats={"share": "pct"})


def test_table_view_applies_table_formats():
    at = AppTest.from_function(_share_chart_script).run()
    at.toggle(key="t_table_view").set_value(True).run()
    styler = at.dataframe[0].proto.arrow_data.styler
    shown = dataframe_util.convert_arrow_bytes_to_pandas_df(styler.display_values)  # the text the grid paints
    assert shown["share"].tolist() == ["20.4%"]  # without formats a float column defaults to money: "0"


def _text_layer(s):
    return next(
        layer for layer in _layers(s) if layer.get("mark") == "text" or layer.get("mark", {}).get("type") == "text"
    )


def test_direct_labels_use_text_color_not_series_color():
    df = pd.DataFrame({"x": ["a", "b"], "y": [1, 2], "s": ["CMP19_01", "CMP19_02"]})
    encoding = _text_layer(spec(df, series="s"))["encoding"]
    assert "color" not in encoding or "field" not in encoding["color"]


def test_labels_on_stacked_bars_follow_the_stack():
    df = pd.DataFrame({"x": ["a", "a"], "y": [1, 2], "s": ["First", "Returning"]})
    layer = _text_layer(build_chart(df, x="x", y="y", x_title="X", y_title="Y", series="s", horizontal=True).to_dict())
    assert layer["encoding"]["x"]["stack"] == "zero"


def _measure_axis(s, channel="y"):
    return next(enc[channel]["axis"] for enc in _encodings(s) if channel in enc and "axis" in enc[channel])


def test_count_measure_gets_whole_number_ticks():
    counts = spec(pd.DataFrame({"x": ["a", "b"], "y": [1, 1]}))
    money = spec(pd.DataFrame({"x": ["a", "b"], "y": [1.5, 2.25]}))
    assert _measure_axis(counts)["format"] == ",d" and _measure_axis(counts)["tickMinStep"] == 1
    assert "format" not in _measure_axis(money)


def test_stacked_bars_and_labels_share_the_legend_order():
    df = pd.DataFrame({"x": ["a", "a"], "y": [103, 13], "s": ["First", "Returning"]})
    s = build_chart(df, x="x", y="y", x_title="X", y_title="Y", series="s", horizontal=True).to_dict()
    bar, text = _layers(s)[0]["encoding"], _text_layer(s)["encoding"]
    assert bar["order"] == text["order"]
    assert text["detail"]["field"] == "s"


def test_multi_series_lines_are_dashed_and_unlabelled():
    df = pd.DataFrame({"x": [1, 2, 1, 2], "y": [1, 2, 3, 4], "s": ["a", "a", "b", "b"]})
    s = spec(df, series="s", kind="line")
    assert any("strokeDash" in enc for enc in _encodings(s))
    assert not has_text_layer(s)
