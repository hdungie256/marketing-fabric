import pytest

from fabric_control.contracts import columns, load_schema
from pipelines.jobs.ingest.reconciliation import load_baselines

seed = pytest.importorskip("sources.seed")


@pytest.mark.parametrize(
    "name, expected",
    [
        ("CustomerID", "customer_id"),
        ("Transaction_Date_ISO", "transaction_date_iso"),
        ("Discount_pct", "discount_pct"),
        ("GST", "gst"),
        ("Sales_Line_ID", "sales_line_id"),
    ],
)
def test_snake(name, expected):
    assert seed.snake(name) == expected


@pytest.mark.parametrize("table", seed.TABLES, ids=lambda t: t.qualified)
def test_rows_match_baselines(table):
    assert len(seed.frame(table)) == load_baselines()[f"raw/{table.source}/{table.name}"]


def test_story_marks():
    counts = {t.name: len(seed.frame(t)) for t in seed.TABLES}
    assert (counts["sales_lines"], counts["customers"], counts["attribution"]) == (52924, 1468, 1290)


@pytest.mark.parametrize("table", seed.TABLES, ids=lambda t: t.qualified)
def test_columns_match_contract(table):
    assert list(seed.frame(table).columns) == [
        name for name, _ in columns(load_schema(f"raw/{table.source}/{table.name}"))
    ]


def test_provenance():
    values = {t.name: set(seed.frame(t)["provenance"]) for t in seed.TABLES}
    assert all(v <= {"original", "synthetic"} for v in values.values())
    for synthetic in ("attribution", "targets", "product_costs", "campaign_spend", "campaigns", "spend_recon"):
        assert values[synthetic] == {"synthetic"}
    for original in ("sales_lines", "customers", "coupon_plan", "daily_spend", "tax_rates"):
        assert values[original] == {"original"}


def test_seed_frames_are_deterministic():
    for table in seed.TABLES:
        assert seed.frame(table).equals(seed.frame(table))


def test_money_rounding():
    costs = seed.frame(next(t for t in seed.TABLES if t.name == "product_costs"))
    assert (costs["observed_avg_price"].round(4) == costs["observed_avg_price"]).all()
    assert (costs["estimated_unit_cost"].round(2) == costs["estimated_unit_cost"]).all()
