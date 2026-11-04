import streamlit as st

import fabric_control
from app.services import product_sales as svc
from app.shell import NOTE_TEXT, Filter, add_footnote, chart, current_source, empty_state, filter_bar, table

KEY = "products_categories"
TREND_KEY = "products_categories_trend"
RANK = {"gross_value": "gross_value", "quantity": "quantity_sold"}


def render() -> None:
    df = svc.load(current_source())
    periods = dict(svc.period_options(df))
    names = dict(svc.campaigns(df))
    labels = {column: fabric_control.term(term_id)["display_name"] for column, term_id in RANK.items()}
    chosen = filter_bar(
        KEY,
        [
            Filter("period", "Period", list(periods), format_func=periods.get),
            Filter(
                "campaign",
                "Campaign",
                list(names),
                format_func=lambda c: names[c] if c == svc.ALL else f"{names[c]} · {c}",
            ),
            Filter("rank_by", "Rank by", list(RANK), format_func=labels.get),
            Filter("top_n", "Top SKUs", svc.TOP_SKUS, default=10, format_func=lambda n: f"Top {n}"),
        ],
    )
    rows = svc.select(df, chosen["period"], chosen["campaign"])
    if rows.empty:
        if chosen["campaign"] == svc.ALL:
            empty_state("No sales in this period.")
        else:
            empty_state(
                f"No attributed sales for {chosen['campaign']} in this period.",
                "Clear the Campaign filter to see all.",
            )
        return
    if chosen["campaign"] == svc.ALL:
        st.caption("Includes sales not attributed to any campaign.")
    by, label = chosen["rank_by"], labels[chosen["rank_by"]]
    chart(
        svc.top_skus(rows, by, chosen["top_n"]),
        key="products_top_skus",
        title=f"Top {chosen['top_n']} SKUs by {label}",
        x="product_sku",
        y=by,
        x_title="SKU",
        y_title=label,
        horizontal=True,
        table_dataset_id=svc.DATASET,
    )
    sums = svc.top_categories(rows, by)
    share = f"Share of {label}"
    categories = sums.assign(**{share: svc.share(sums, by)}).rename(
        columns={"canonical_category": "Category", "gross_value": labels["gross_value"], "quantity": labels["quantity"]}
    )
    st.markdown(f"**Categories by {label}**")
    table(
        categories,
        dataset_id=svc.DATASET,
        formats={share: "pct"},
        info_terms={labels["gross_value"]: "gross_value", labels["quantity"]: "quantity_sold"},
    )
    trend_n = filter_bar(
        TREND_KEY,
        [Filter("n", "Categories in trend", svc.TREND_CATEGORIES, default=4, format_func=lambda n: f"Top {n}")],
    )["n"]
    chart(
        svc.trend(rows, trend_n, by),
        key="products_trend",
        title=f"Monthly trend — top {trend_n} categories by {label}",
        x="month",
        y=by,
        x_title="Month",
        y_title=label,
        series="canonical_category",
        kind="line",
        table_dataset_id=svc.DATASET,
    )
    add_footnote(NOTE_TEXT["currency_unverified"])
