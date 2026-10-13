import streamlit as st

from app.shell import current_source, empty_state, metric, table

CAMPAIGNS = "mart_finance.contribution"
SKUS = "mart_finance.contribution_sku"
SKU_COLUMNS = [
    "campaign_id", "product_sku", "product_description", "quantity", "attributed_gross_value",
    "estimated_unit_cost", "reference_cogs", "estimated_unit_cost__denied", "reference_cogs__denied",
]  # fmt: skip


def render() -> None:
    source = current_source()
    campaigns, skus = source.read(CAMPAIGNS), source.read(SKUS)
    if campaigns.empty:
        empty_state("No contribution yet.", "Contribution fills after the finance marts refresh.")
        return
    fresh = max(campaigns["_refreshed_at"].max(), skus["_refreshed_at"].max())
    left, right = st.columns(2)
    with left:
        metric("estimated_contribution", campaigns["estimated_contribution"].sum(), fresh, kind="money")
    with right:
        metric("reference_cost_of_goods", campaigns["reference_cogs"].sum(), fresh, kind="money")

    st.markdown("**Estimated contribution by campaign**")
    table(
        campaigns.drop(columns=["skus_without_cost"]),
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
