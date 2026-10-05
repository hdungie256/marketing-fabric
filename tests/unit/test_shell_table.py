import importlib
import math

import pandas as pd
import pytest
from streamlit.testing.v1 import AppTest

import fabric_control
from app.shell.table import DENIED_TEXT, prepare_table

# app.shell re-exports the `table` function, which shadows the submodule attribute.
table_module = importlib.import_module("app.shell.table")


def test_denied_cells_are_replaced_and_flag_column_dropped():
    df = pd.DataFrame({"sku_cost": [10.0, 20.0], "sku_cost__denied": [True, False]})
    out, _, _ = prepare_table(df)
    assert list(out.columns) == ["sku_cost"]
    assert out["sku_cost"].tolist() == [DENIED_TEXT, 20.0]


def test_nan_denied_flag_counts_as_allowed():
    df = pd.DataFrame({"sku_cost": [10.0], "sku_cost__denied": [math.nan]})
    out, _, _ = prepare_table(df)
    assert out["sku_cost"].tolist() == [10.0]


def test_masked_columns_get_lock_prefix_and_keep_none():
    df = pd.DataFrame({"customer_id": ["C****42", None]})
    out, _, _ = prepare_table(df, masked_cols=frozenset({"customer_id"}))
    # pandas may normalise None to NaN in string columns; either way it stays missing, unprefixed.
    assert out["customer_id"].iloc[0] == "🔒 C****42"
    assert pd.isna(out["customer_id"].iloc[1])


def test_technical_columns_are_hidden():
    df = pd.DataFrame({"orders": [1], "_refreshed_at": [pd.Timestamp("2026-10-05")], "_run_id": ["r1"]})
    out, _, _ = prepare_table(df)
    assert list(out.columns) == ["orders"]


def test_campaign_cell_combines_name_and_code():
    df = pd.DataFrame({"campaign_id": ["CMP-01"], "campaign_name": ["Spring Sale"], "orders": [3]})
    out, _, _ = prepare_table(df, campaign_col="campaign_id")
    assert list(out.columns) == ["campaign_id", "orders"]
    assert out["campaign_id"].tolist() == ["Spring Sale · CMP-01"]


def test_numeric_columns_are_formatted_and_right_aligned():
    df = pd.DataFrame({"orders": [1290], "value": [12345.6], "ratio": [3.4178], "name": ["x"]})
    out, formatters, config = prepare_table(df, formats={"ratio": "ratio"})
    assert formatters["orders"](1290) == "1,290"
    assert formatters["value"](12345.6) == "12,346"
    assert formatters["ratio"](3.4178) == "3.42×"
    assert "name" not in formatters
    assert config["orders"]["alignment"] == "right"
    assert config["orders"]["type_config"]["type"] == "number"


def test_formatter_passes_strings_through():
    df = pd.DataFrame({"sku_cost": [10.0, 20.0], "sku_cost__denied": [True, False]})
    _, formatters, config = prepare_table(df)
    assert formatters["sku_cost"](DENIED_TEXT) == DENIED_TEXT
    assert config["sku_cost"]["type_config"]["type"] == "text"
    assert config["sku_cost"]["alignment"] == "right"


def test_unknown_format_is_rejected():
    with pytest.raises(ValueError, match="orders: unknown format 'currency'"):
        prepare_table(pd.DataFrame({"orders": [1]}), formats={"orders": "currency"})


def test_empty_frame_is_fine():
    out, _, _ = prepare_table(pd.DataFrame({"orders": pd.Series([], dtype="int64")}))
    assert out.empty


def test_masked_columns_read_effective_policy_for_role(monkeypatch):
    monkeypatch.setattr(
        fabric_control,
        "effective_matrix",
        lambda: [
            {"role": "UG03", "dataset_id": "mart_customer/rfm", "column": "customer_id", "action": "mask:partial"},
            {"role": "UG03", "dataset_id": "mart_customer/rfm", "column": "segment", "action": "allow"},
            {"role": "UG02", "dataset_id": "mart_customer/rfm", "column": "email", "action": "mask:partial"},
        ],
    )
    assert table_module.masked_columns("UG03", "mart_customer/rfm") == frozenset({"customer_id"})


def _table_script():
    import pandas as pd

    from app.shell import session, table

    session.set_role("UG03")
    table(pd.DataFrame({"customer_id": ["C****42"], "orders": [3]}), dataset_id="mart_customer/rfm")


def test_table_renders_masked_value(monkeypatch):
    monkeypatch.setattr(
        fabric_control,
        "effective_matrix",
        lambda: [
            {"role": "UG03", "dataset_id": "mart_customer/rfm", "column": "customer_id", "action": "mask:partial"}
        ],
    )
    table_module._cached_masked_columns.clear()
    at = AppTest.from_function(_table_script).run()
    assert not at.exception
    assert at.dataframe[0].value["customer_id"].tolist() == ["🔒 C****42"]


def test_table_propagates_policy_errors(monkeypatch):
    def boom():
        raise RuntimeError("policy unavailable")

    monkeypatch.setattr(fabric_control, "effective_matrix", boom)
    table_module._cached_masked_columns.clear()
    at = AppTest.from_function(_table_script).run()
    assert "policy unavailable" in at.exception[0].message
