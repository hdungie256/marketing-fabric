import fabric_control
from app.services import campaign_overview as overview
from app.services import product_sales as svc
from app.shell import NOTE_TEXT, Filter, add_footnote, chart, current_source, empty_state, filter_bar, table

KEY = "products_categories"
RANK = {"gross_value": "gross_value", "quantity": "quantity_sold"}


def render() -> None:
    df = svc.load(current_source())
    periods = dict(svc.period_options(df))
    names = dict(overview.campaigns(df))
    labels = {column: fabric_control.term(term_id)["display_name"] for column, term_id in RANK.items()}
    chosen = filter_bar(
        KEY,
        [
            Filter("period", "Period", list(periods), format_func=periods.get),
            Filter(
                "campaign",
                "Campaign",
                list(names),
                format_func=lambda c: names[c] if c == overview.ALL else f"{names[c]} · {c}",
            ),
            Filter("rank_by", "Rank by", list(RANK), format_func=labels.get),
        ],
    )
    rows = svc.select(df, chosen["period"], chosen["campaign"])
    if rows.empty:
        if chosen["campaign"] == overview.ALL:
            empty_state("No sales in this period.")
        else:
            empty_state(
                f"No attributed sales for {chosen['campaign']} in this period.",
                "Clear the Campaign filter to see all.",
            )
        return
    by, label = chosen["rank_by"], labels[chosen["rank_by"]]
    chart(
        svc.top_skus(rows, by),
        key="products_top_skus",
        title="Top 10 SKUs",
        x="product_sku",
        y=by,
        x_title="SKU",
        y_title=label,
        horizontal=True,
        table_dataset_id=svc.DATASET,
    )
    categories = svc.top_categories(rows, by).rename(
        columns={"canonical_category": "Category", "gross_value": labels["gross_value"], "quantity": labels["quantity"]}
    )
    table(
        categories,
        dataset_id=svc.DATASET,
        info_terms={"Gross Value": "gross_value", "Quantity Sold": "quantity_sold"},
    )
    chart(
        svc.trend(rows),
        key="products_trend",
        title="Monthly trend — top 4 categories",
        x="month",
        y=by,
        x_title="Month",
        y_title=label,
        series="canonical_category",
        kind="line",
        table_dataset_id=svc.DATASET,
    )
    add_footnote(NOTE_TEXT["currency_unverified"])
