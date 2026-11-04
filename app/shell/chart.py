import altair as alt
import pandas as pd
import streamlit as st

from app.shell.table import table
from app.shell.theme import CAMPAIGN_COLORS

# DESIGN.md colors.series-1..5
SERIES_COLORS = ["#2a78d6", "#d95926", "#1baf7a", "#4a3aa7", "#eda100"]
GRID_COLOR = "#E4E7EC"  # DESIGN.md colors.border
TEXT_COLOR = "#1A1F29"  # DESIGN.md colors.text; series hues are never used as text color
MAX_LABELLED_SERIES = 4


def _color_scale(values: list[str]) -> alt.Scale:
    if all(v in CAMPAIGN_COLORS for v in values):
        return alt.Scale(domain=values, range=[CAMPAIGN_COLORS[v] for v in values])
    return alt.Scale(domain=values, range=[SERIES_COLORS[i % len(SERIES_COLORS)] for i in range(len(values))])


def build_chart(
    df: pd.DataFrame,
    *,
    x: str,
    y: str,
    x_title: str,
    y_title: str,
    series: str | None = None,
    kind: str = "bar",
    horizontal: bool = False,
) -> alt.Chart | alt.LayerChart:
    """x is the category/time axis, y the measure; horizontal puts the category on the vertical axis."""
    if kind not in ("bar", "line"):
        raise ValueError(f"kind must be 'bar' or 'line', got {kind!r}")
    # a count measure gets whole-number ticks: no 0.2 buyers on the axis
    measure_axis = {"gridColor": GRID_COLOR}
    if pd.api.types.is_integer_dtype(df[y]):
        measure_axis |= {"format": ",d", "tickMinStep": 1}
    if horizontal:
        enc: dict = {
            "y": alt.Y(x, title=x_title, sort="-x", axis=alt.Axis(grid=False)),
            "x": alt.X(y, title=y_title, axis=alt.Axis(**measure_axis)),
        }
    else:
        enc = {
            "x": alt.X(x, title=x_title, axis=alt.Axis(grid=False)),
            "y": alt.Y(y, title=y_title, axis=alt.Axis(**measure_axis)),
        }
    enc["tooltip"] = [x, y] + ([series] if series else [])
    n_series = df[series].nunique() if series else 1
    stacked = kind == "bar" and series is not None and df.groupby(x)[series].nunique().max() > 1
    if series:
        values = list(dict.fromkeys(df[series].astype(str)))
        enc["color"] = alt.Color(series, scale=_color_scale(values), legend=alt.Legend(title=None))
        if kind == "line":
            # close lines stay apart without relying on hue alone
            enc["strokeDash"] = alt.StrokeDash(series, legend=alt.Legend(title=None))
        if stacked:
            # bars and their labels stack in the same (legend) order, else a label lands on the wrong segment
            df = df.assign(_stack_order=df[series].astype(str).map({v: i for i, v in enumerate(values)}))
            enc["order"] = alt.Order("_stack_order:Q", sort="ascending")
    base = alt.Chart(df).encode(**enc)
    mark = base.mark_bar() if kind == "bar" else base.mark_line(point=True)
    # several lines with a label on every point turn into clutter: read values from the tooltip instead
    if n_series > MAX_LABELLED_SERIES or (kind == "line" and n_series > 1):
        return mark
    # bars of one category stacked across series: text marks do not stack by default, so stack them too
    label_enc = {k: v for k, v in enc.items() if k not in ("color", "strokeDash")}
    measure = "x" if horizontal else "y"
    if stacked:
        label_enc[measure] = (alt.X if horizontal else alt.Y)(y, stack="zero")
        label_enc["detail"] = alt.Detail(series)
        # the stacked label sits at the segment end: pull it back inside the segment
        text_kw = {"align": "right", "dx": -4} if horizontal else {"baseline": "top", "dy": 4}
    else:
        text_kw = {"align": "left", "dx": 4} if horizontal else {"dy": -6}
    labels = alt.Chart(df).mark_text(color=TEXT_COLOR, **text_kw).encode(**label_enc, text=alt.Text(y, format=",.0f"))
    if stacked:
        # a zero-value segment has no room for its label
        labels = labels.transform_filter(f"datum['{y}'] > 0")
    return mark + labels


def chart(
    df: pd.DataFrame,
    *,
    key: str,
    title: str,
    x: str,
    y: str,
    x_title: str,
    y_title: str,
    series: str | None = None,
    kind: str = "bar",
    horizontal: bool = False,
    table_dataset_id: str | None = None,
) -> None:
    st.markdown(f"**{title}**")
    if st.toggle("Table view", key=f"{key}_table_view"):
        table(df, dataset_id=table_dataset_id)
        return
    st.altair_chart(
        build_chart(df, x=x, y=y, x_title=x_title, y_title=y_title, series=series, kind=kind, horizontal=horizontal),
        use_container_width=True,
    )
