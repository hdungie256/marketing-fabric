"""Story 2.1 tests: term IDs, fragment validation, synthetic propagation, sync."""

import pytest
import yaml

import fabric_control as fc
from fabric_control.clients import openmetadata
from fabric_control.glossary import (
    GlossaryError,
    labelled_terms,
    load_tags,
    load_terms,
    synthetic_closure,
    term_id,
)

TERM = {
    "display_name": "Gross Value",
    "owner_slice": "customer",
    "dataset_id": "unified/orders",
    "column": "gross_value",
    "definition": "d",
    "formula": "f",
    "rules": ["R2"],
    "limitations": ["l"],
    "notes": ["n"],
}


def write_glossary(path, terms):
    path.write_text(yaml.safe_dump({"terms": terms}))


def test_term_id_follows_ad16():
    assert term_id("Attributed Value / Spend Ratio") == "attributed_value_per_spend_ratio"
    assert term_id("Gross Value") == "gross_value"
    assert term_id("RFM Segment") == "rfm_segment"


def test_repo_customer_terms_load_with_computed_provenance():
    terms = labelled_terms()
    assert {t["display_name"] for t in terms.values()} >= {
        "Gross Value",
        "First Observed Buyers",
        "RFM Segment",
        "Estimated Unit Cost",
    }
    assert terms["estimated_unit_cost"]["provenance"] == "synthetic"
    assert terms["gross_value"]["provenance"] == "original"
    assert terms["first_observed_buyers"]["provenance"] == "original"


def test_duplicate_term_id_names_both_files(tmp_path):
    (tmp_path / "glossary").mkdir()
    (tmp_path / "tags").mkdir()
    write_glossary(tmp_path / "glossary" / "a.yml", [TERM])
    write_glossary(tmp_path / "glossary" / "b.yml", [TERM])
    with pytest.raises(GlossaryError, match="a.yml.*b.yml|b.yml.*a.yml"):
        load_terms(tmp_path)


def test_duplicate_term_names_display_and_both_files(tmp_path):
    (tmp_path / "glossary").mkdir()
    other = {**TERM, "column": "shipping_fee"}
    write_glossary(tmp_path / "glossary" / "a.yml", [TERM])
    write_glossary(tmp_path / "glossary" / "b.yml", [other])
    with pytest.raises(GlossaryError, match="Gross Value.*a.yml.*b.yml|Gross Value.*b.yml.*a.yml"):
        load_terms(tmp_path)


def test_missing_field_and_dangling_links_fail(tmp_path):
    (tmp_path / "glossary").mkdir()
    broken = {k: v for k, v in TERM.items() if k != "formula"}
    write_glossary(tmp_path / "glossary" / "a.yml", [broken])
    with pytest.raises(GlossaryError, match="missing"):
        load_terms(tmp_path)
    write_glossary(tmp_path / "glossary" / "a.yml", [{**TERM, "dataset_id": "unified/nope"}])
    with pytest.raises(GlossaryError, match="unregistered dataset"):
        load_terms(tmp_path)
    write_glossary(tmp_path / "glossary" / "a.yml", [{**TERM, "column": "nope"}])
    with pytest.raises(GlossaryError, match="unknown column"):
        load_terms(tmp_path)
    write_glossary(tmp_path / "glossary" / "a.yml", [{**TERM, "limitations": [{"Not ROAS": "sample"}]}])
    with pytest.raises(GlossaryError, match="must be strings"):
        load_terms(tmp_path)


def project(tmp_path):
    (tmp_path / "contracts" / "datasets").mkdir(parents=True)
    datasets = [
        {"dataset_id": "raw/sales/lines", "job_id": "ingest/sales"},
        {"dataset_id": "raw/campaign/campaigns", "job_id": "ingest/campaign"},
        {"dataset_id": "raw/campaign/targets", "job_id": "ingest/campaign"},
        {"dataset_id": "unified/orders", "job_id": "unified/orders"},
        {"dataset_id": "unified/targets_clean", "job_id": "unified/targets_clean"},
    ]
    (tmp_path / "contracts" / "datasets" / "all.yml").write_text(yaml.safe_dump({"datasets": datasets}))
    jobs = {
        "ingest/sales": ("[]", ["raw/sales/lines"]),
        "ingest/campaign": ("[]", ["raw/campaign/campaigns", "raw/campaign/targets"]),
        "unified/orders": (["raw/sales/lines"], ["unified/orders"]),
        "unified/targets_clean": (["raw/campaign/targets"], ["unified/targets_clean"]),
    }
    for job_id, (inputs, outputs) in jobs.items():
        path = tmp_path / "pipelines" / "jobs" / job_id / "job.py"
        path.parent.mkdir(parents=True)
        path.write_text(f"INPUTS = {inputs!r}\nOUTPUTS = {outputs!r}\n")
    return tmp_path


def test_synthetic_closure_does_not_leak_to_original_siblings(tmp_path):
    root = project(tmp_path)
    registry = {
        "raw/sales/lines": {},
        "raw/campaign/campaigns": {},
        "raw/campaign/targets": {"synthetic_source": True},
        "unified/orders": {},
        "unified/targets_clean": {},
    }
    assert synthetic_closure(registry, root) == {"raw/campaign/targets", "unified/targets_clean"}


def test_load_tags_and_duplicate_detection(tmp_path):
    (tmp_path / "tags").mkdir()
    tag = {"name": "direct_identifier", "classification": "Sensitivity", "description": "d"}
    (tmp_path / "tags" / "a.yml").write_text(yaml.safe_dump({"tags": [tag]}))
    assert load_tags(tmp_path) == {("Sensitivity", "direct_identifier"): {**tag, "_file": "a.yml"}}
    (tmp_path / "tags" / "b.yml").write_text(yaml.safe_dump({"tags": [tag]}))
    with pytest.raises(GlossaryError, match="a.yml.*b.yml|b.yml.*a.yml"):
        load_tags(tmp_path)


@pytest.fixture
def online_repo(monkeypatch):
    monkeypatch.setenv("FABRIC_CONTROL_MODE", "online")


def test_sync_glossary_offline_validates_without_calling_om(monkeypatch):
    def fail(*args, **kwargs):
        raise AssertionError("OM called in offline mode")

    monkeypatch.setattr(openmetadata, "put_glossary", fail)
    monkeypatch.setattr(openmetadata, "put_glossary_term", fail)
    assert fc.sync_glossary() is None


def test_sync_glossary_online_pushes_terms_with_source_linkage(online_repo, monkeypatch):
    calls = []
    monkeypatch.setattr(openmetadata, "put_glossary", lambda *a: calls.append(("glossary", a)) or "g1")
    monkeypatch.setattr(openmetadata, "put_glossary_term", lambda *a: calls.append(("term", a)) or "t1")
    fc.sync_glossary()
    assert calls[0][0] == "glossary"
    assert calls[0][1][0] == "marketing_metrics"
    pushed = {c[1][1]: c[1][3] for c in calls if c[0] == "term"}
    assert set(pushed) >= {"gross_value", "estimated_unit_cost"}
    assert "unified/orders.gross_value" in pushed["gross_value"]


def test_sync_tags_online_pushes_taxonomy_once_per_classification(online_repo, monkeypatch):
    calls = []
    monkeypatch.setattr(openmetadata, "put_classification", lambda *a: calls.append(("classification", a)))
    monkeypatch.setattr(openmetadata, "put_tag", lambda *a: calls.append(("tag", a)))
    fc.sync_tags()
    assert sorted({c[1][0] for c in calls if c[0] == "classification"}) == ["Finance", "Sensitivity"]
    pushed = {(c[1][0], c[1][1]) for c in calls if c[0] == "tag"}
    assert pushed >= {("Sensitivity", "direct_identifier"), ("Finance", "cost_estimate")}


def test_sync_survives_openmetadata_outage(online_repo, monkeypatch):
    def down(*args, **kwargs):
        raise ConnectionRefusedError("down")

    monkeypatch.setattr(openmetadata, "put_glossary", down)
    monkeypatch.setattr(openmetadata, "put_classification", down)
    assert fc.sync_glossary() is None
    assert fc.sync_tags() is None
