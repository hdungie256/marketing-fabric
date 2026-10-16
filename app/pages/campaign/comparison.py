import fabric_control
from app.services import comparison as svc
from app.shell import NOTE_TEXT, Filter, add_footnote, chart, current_source, filter_bar, table

KEY = "campaign_comparison"
COMPARE_BY = {"campaign": "Campaign", "channel": "Channel"}


def render() -> None:
    df = svc.load(current_source())
    periods = dict(svc.periods(df))
    labels = {m: fabric_control.term(m)["display_name"] for m in svc.METRICS}
    chosen = filter_bar(
        KEY,
        [
            Filter("period", "Period", list(periods), format_func=periods.get),
            Filter("compare_by", "Compare by", list(COMPARE_BY), format_func=COMPARE_BY.get),
            Filter("metric", "Metric", svc.METRICS, format_func=labels.get),
        ],
    )
    rows = svc.select(df, chosen["period"], chosen["compare_by"])
    metric, compare = chosen["metric"], COMPARE_BY[chosen["compare_by"]]
    chart(
        rows,
        key="comparison_chart",
        title=f"{labels[metric]} by {compare}",
        x="group_name",
        y=metric,
        x_title=compare,
        y_title=labels[metric],
        series="group_id",
        horizontal=True,
        table_dataset_id=svc.DATASET,
    )
    if chosen["compare_by"] == "campaign":
        shown = rows[["group_id", "group_name", "channel", *svc.METRICS]].rename(
            columns={"group_id": "Campaign", "group_name": "campaign_name", "channel": "Channel", **labels}
        )
        campaign_col = "Campaign"
    else:
        shown = rows[["group_name", *svc.METRICS]].rename(columns={"group_name": "Channel", **labels})
        campaign_col = None
    table(
        shown,
        dataset_id=svc.DATASET,
        campaign_col=campaign_col,
        info_terms={
            "Attributed Gross Value": "attributed_gross_value",
            "Attributed Orders": "attributed_orders",
            "Attributed Buyers": "attributed_buyers",
            "Average Order Value": "average_order_value",
        },
    )
    add_footnote(NOTE_TEXT["currency_unverified"])
