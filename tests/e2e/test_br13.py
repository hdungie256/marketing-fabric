"""BR13: catalog search finds the ratio term with definition, Not ROAS and synthetic label."""

import fabric_control


def test_search_ratio_term_and_definition():
    hits = fabric_control.search("Attributed Value / Spend Ratio")
    assert [h["id"] for h in hits if h["kind"] == "term"] == ["attributed_value_per_spend_ratio"]
    term = fabric_control.term("attributed_value_per_spend_ratio")
    assert term["display_name"] == "Attributed Value / Spend Ratio"
    assert term["formula"] and term["dataset_id"] and term["column"] and term["owner_slice"]
    assert any("roas" in item.lower() for item in term["limitations"])
    assert term["synthetic"] is True


def test_catalog_browses_all_layers():
    layers = {item["layer"] for item in fabric_control.catalog()}
    assert {"raw", "unified", "mart"} <= layers
