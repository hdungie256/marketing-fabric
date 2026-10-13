import pytest
from streamlit.testing.v1 import AppTest

import fabric_control
from app.pages.governance.access_matrix import ALL, color, matrix
from app.shell.registry import load_pages, validate

ROWS = [
    {"role": "UG03", "dataset_id": "mart_finance.contribution_sku", "column": "sku_cost", "action": "deny"},
    {"role": "UG04", "dataset_id": "mart_finance.contribution_sku", "column": "sku_cost", "action": "allow"},
    {"role": "UG01", "dataset_id": "mart_shared.orders", "column": "customer_id", "action": "mask:partial"},
    {"role": "UG02", "dataset_id": "mart_shared.orders", "column": "customer_id", "action": "allow"},
]


def test_matrix_is_role_by_dataset_column_with_icon_and_word():
    grid = matrix(ROWS)
    assert list(grid.columns) == [
        "Dataset",
        "Column",
        "Marketing Analyst (UG01)",
        "CRM / Customer Marketing (UG02)",
        "Marketing Manager (UG03)",
        "Finance / Business Controller (UG04)",
    ]
    sku = grid[grid["Column"] == "sku_cost"].iloc[0]
    assert (sku["Marketing Manager (UG03)"], sku["Finance / Business Controller (UG04)"]) == ("⊘ deny", "✓ allow")
    customer = grid[grid["Column"] == "customer_id"].iloc[0]
    assert customer["Marketing Analyst (UG01)"] == "◐ mask"


def test_matrix_filters_one_dataset():
    assert set(matrix(ROWS, "mart_shared.orders")["Dataset"]) == {"mart_shared.orders"}
    assert len(matrix(ROWS, ALL)) == 2


def test_every_cell_has_a_color():
    assert all(color(text) for text in ("✓ allow", "◐ mask", "⊘ deny"))


def test_page_is_registered_for_data_steward_only():
    pages = [p for p in load_pages() if p.key == "access_matrix"]
    validate(pages)
    assert [p.roles for p in pages] == [frozenset({"UG05"})]


def _script():
    from app.pages.governance.access_matrix import render
    from app.shell import session

    session.set_role("UG05")
    render()


@pytest.mark.parametrize("rows,expected", [(ROWS, 1), ([], 0)])
def test_page_renders_grid_or_empty_state(monkeypatch, rows, expected):
    monkeypatch.setattr(fabric_control, "effective_matrix", lambda: rows)
    at = AppTest.from_function(_script).run()
    assert not at.exception
    assert len(at.dataframe) == expected
