"""RFM Segments (Story 5.1, BR05). Home page of UG02."""

from app.services import customers as svc
from app.shell import Filter, chart, current_source, empty_state, filter_bar, table

KEY = "rfm_segments"


def render() -> None:
    df = svc.load(current_source())
    if df.empty:
        empty_state("No buying customers in this data.")
        return
    summary = svc.segment_summary(df)
    chart(
        summary,
        key="rfm_distribution",
        title="Buyers by RFM segment",
        x="segment",
        y="customers",
        x_title="Segment",
        y_title="Buyers",
        table_dataset_id=svc.DATASET,
    )
    table(summary, dataset_id=svc.DATASET, formats={"customers": "count", "share": "pct"})
    values = filter_bar(KEY, [Filter("segment", "Segment", list(summary["segment"]))])
    rows = svc.match(df, segment=values["segment"])
    table(
        rows,
        dataset_id=svc.DATASET,
        formats={"monetary_value": "money"},
        info_terms={"segment": "rfm_segment"},
    )
