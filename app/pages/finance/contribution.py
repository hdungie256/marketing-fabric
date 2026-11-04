import altair as alt
import pandas as pd
import streamlit as st

import fabric_control
from app.pages.finance.budget_spend import ACCENT
from app.shell import STATUS_COLORS, current_in_flight, current_source, empty_state, fmt_money, metric, table, watch
from app.shell.chart import TEXT_COLOR

CAMPAIGNS = "mart_finance.contribution"
SKUS = "mart_finance.contribution_sku"
SKU_COLUMNS = [
    "campaign_id", "product_sku", "product_description", "quantity", "attributed_gross_value",
    "estimated_unit_cost", "reference_cogs", "estimated_unit_cost__denied", "reference_cogs__denied",
]  # fmt: skip
# DESIGN.md has no diverging pair; accent vs danger passes the colorblind check that success vs danger fails
SIGNS = {"Positive": ACCENT, "Negative": STATUS_COLORS["danger"]}


def contribution_bars(campaigns: pd.DataFrame) -> alt.LayerChart:
    """Sorted bars around a zero rule; the signed label and the side of zero carry the sign, not only the color."""
    value = campaigns["estimated_contribution"].astype(float)
    d = pd.DataFrame(
        {
            "campaign": campaigns["campaign_name"] + " · " + campaigns["campaign_id"],
            "value": value,
            "sign": ["Negative" if v < 0 else "Positive" for v in value],
            "label": campaigns["estimated_contribution"].map(fmt_money),
        }
    ).sort_values("value", ascending=False)
    title = fabric_control.term("estimated_contribution")["display_name"]
    x = alt.X("value:Q", title=title)
    y = alt.Y("campaign:N", sort=list(d["campaign"]), title=None, axis=alt.Axis(labelLimit=240))
    color = alt.Color(
        "sign:N",
        scale=alt.Scale(domain=list(SIGNS), range=list(SIGNS.values())),
        legend=alt.Legend(title=None, orient="top"),
    )
    tooltip = [alt.Tooltip("campaign:N", title="Campaign"), alt.Tooltip("label:N", title=title)]
    base = alt.Chart(d).encode(x=x, y=y)
    bars = base.mark_bar().encode(color=color, tooltip=tooltip)
    zero = alt.Chart(pd.DataFrame({"value": [0]})).mark_rule(color=STATUS_COLORS["muted"]).encode(x=x)
    labels = base.encode(text="label:N")
    gains = labels.transform_filter("datum.value >= 0").mark_text(align="left", dx=4, color=TEXT_COLOR)
    losses = labels.transform_filter("datum.value < 0").mark_text(align="right", dx=-4, color=TEXT_COLOR)
    return (bars + zero + gains + losses).properties(height=alt.Step(36))


def render() -> None:
    source = current_source()
    campaigns, skus = source.read(CAMPAIGNS), source.read(SKUS)
    if campaigns.empty:
        empty_state("No contribution yet.", "Contribution fills after the finance marts refresh.")
        return
    fresh = max(campaigns["_refreshed_at"].max(), skus["_refreshed_at"].max())
    shown = current_in_flight(None)
    left, right = st.columns(2)
    with left:
        metric(
            "estimated_contribution", campaigns["estimated_contribution"].sum(), fresh, kind="money", in_flight=shown
        )
    with right:
        metric("reference_cost_of_goods", campaigns["reference_cogs"].sum(), fresh, kind="money", in_flight=shown)
    if shown:
        watch(None, shown)

    st.markdown("**Estimated contribution by campaign**")
    st.altair_chart(contribution_bars(campaigns), width="stretch")
    table(
        campaigns.drop(columns=["skus_without_cost", "provenance"]),
        dataset_id=CAMPAIGNS,
        campaign_col="campaign_id",
    )

    st.markdown("**Reference cost of goods by SKU**")
    table(skus[[c for c in SKU_COLUMNS if c in skus.columns]], dataset_id=SKUS, formats={"quantity": "count"})

    st.markdown("**Items not yet available**")
    missing = skus[~skus["cost_available"].astype(bool)]
    if missing.empty:
        st.caption("Every attributed SKU has a reference cost; nothing is missing from the estimate.")
    else:
        st.caption(f"{len(missing)} SKUs have no reference cost and add no cost of goods to the estimate.")
        table(missing[["campaign_id", "product_sku", "product_description", "attributed_gross_value"]], dataset_id=SKUS)
