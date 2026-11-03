import json

import pytest
from streamlit.testing.v1 import AppTest

import fabric_control
from app.pages.governance import access_matrix
from app.pages.governance.access_matrix import ALL, color, matrix, policy_columns
from app.shell.registry import load_pages, validate
from fabric_control.policy import Policy

ROWS = [
    {"role": "UG03", "dataset_id": "mart_finance.contribution_sku", "column": "sku_cost", "action": "deny"},
    {"role": "UG04", "dataset_id": "mart_finance.contribution_sku", "column": "sku_cost", "action": "allow"},
    {"role": "UG01", "dataset_id": "mart_shared.orders", "column": "customer_id", "action": "mask:partial"},
    {"role": "UG02", "dataset_id": "mart_shared.orders", "column": "customer_id", "action": "allow"},
]
POLICY = Policy(
    roles={code: code.lower() for code in ("UG01", "UG02", "UG03", "UG04")},
    readers={},
    actions={
        "Finance.sku_cost": {"default": "deny", "UG04": "allow"},
        "Sensitivity.direct_identifier": {"default": "mask:partial", "UG02": "allow"},
        "Sensitivity.internal": {"default": "allow"},
    },
    column_tags={
        "mart_finance.contribution_sku": {"sku_cost": "Finance.sku_cost", "quantity": "Sensitivity.internal"},
        "mart_shared.orders": {"customer_id": "Sensitivity.direct_identifier"},
        "app.segments": {"name": "Sensitivity.internal"},
    },
)


def test_matrix_is_role_by_dataset_column_with_icon_and_word():
    grid = matrix(ROWS)
    assert list(grid.columns) == ["Dataset", "Column", "UG01", "UG02", "UG03", "UG04"]
    sku = grid[grid["Column"] == "sku_cost"].iloc[0]
    assert (sku["UG03"], sku["UG04"]) == ("⊘ deny", "✓ allow")
    customer = grid[grid["Column"] == "customer_id"].iloc[0]
    assert customer["UG01"] == "◐ mask"


def test_policy_columns_are_those_a_tag_masks_or_denies(monkeypatch):
    monkeypatch.setattr(access_matrix, "load_policy", lambda: POLICY)
    assert policy_columns() == {("mart_finance.contribution_sku", "sku_cost"), ("mart_shared.orders", "customer_id")}


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
    monkeypatch.setattr(access_matrix, "load_policy", lambda: POLICY)
    at = AppTest.from_function(_script).run()
    assert not at.exception
    assert len(at.dataframe) == expected


INTERNAL = [
    {"role": "UG04", "dataset_id": "mart_finance.contribution_sku", "column": "quantity", "action": "allow"},
    {"role": "UG01", "dataset_id": "app.segments", "column": "name", "action": "allow"},
]


def test_page_shows_policy_columns_until_show_all(monkeypatch):
    monkeypatch.setattr(fabric_control, "effective_matrix", lambda: ROWS + INTERNAL)
    monkeypatch.setattr(access_matrix, "load_policy", lambda: POLICY)
    at = AppTest.from_function(_script).run()
    assert not at.exception, at.exception
    grid = at.dataframe[0]
    assert list(grid.value["Column"]) == ["sku_cost", "customer_id"]
    assert list(grid.value.columns) == ["Dataset", "Column", "UG01", "UG02", "UG03", "UG04"]
    assert json.loads(grid.proto.columns)["UG04"]["help"] == "Finance / Business Controller (UG04)"
    legend = (
        "UG01 Marketing Analyst · UG02 CRM / Customer Marketing · "
        "UG03 Marketing Manager · UG04 Finance / Business Controller"
    )
    assert legend in [c.value for c in at.caption]
    at.selectbox(key="_filter_access_matrix_dataset").set_value("app.segments").run()
    assert not at.dataframe
    assert ":material/info: No column in app.segments has a mask or deny tag." in [m.value for m in at.markdown]
    at.toggle(key="access_matrix_all_columns").set_value(True).run()
    assert list(at.dataframe[0].value["Column"]) == ["name"]
    at.selectbox(key="_filter_access_matrix_dataset").set_value(ALL).run()
    assert sorted(at.dataframe[0].value["Column"]) == ["customer_id", "name", "quantity", "sku_cost"]
