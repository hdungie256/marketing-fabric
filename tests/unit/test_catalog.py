from datetime import UTC, datetime

import pytest
import yaml

import fabric_control as fc
from fabric_control.clients import openmetadata, postgres
from fabric_control.clients.http import HttpError
from fabric_control.glossary import synthetic_closure

DATASETS = {
    "raw/sales/lines": ("ingest/sales", "lake_raw.default.lake.lines", [], False),
    "raw/campaign/attribution": ("ingest/campaign", "lake_raw.default.lake.attribution", [], True),
    "unified/orders": ("unified/orders", "lake_unified.default.lake.orders", ["raw/sales/lines"], False),
    "unified/attribution": (
        "unified/attribution",
        "lake_unified.default.lake.attribution",
        ["raw/campaign/attribution"],
        False,
    ),
    "mart_campaign.overview": (
        "marts/campaign/overview",
        "serving.serving.mart_campaign.overview",
        ["unified/orders", "unified/attribution"],
        False,
    ),
}
TERM = {"owner_slice": "campaign", "rules": ["R6"], "limitations": [], "notes": ["attributed_not_incremental"]}
TERMS = [
    {
        **TERM,
        "display_name": "Attributed Orders",
        "definition": "Orders linked to a campaign",
        "formula": "count(distinct canonical_order_id)",
        "dataset_id": "mart_campaign.overview",
        "column": "attributed_orders",
    },
    {
        **TERM,
        "display_name": "Attributed Value / Spend Ratio",
        "definition": "Attributed gross value divided by spend, not ROAS",
        "formula": "attributed_gross_value / spend",
        "dataset_id": "unified/orders",
        "column": "gross_value",
    },
]
COLUMNS = ["attributed_orders", "gross_value"]


@pytest.fixture
def files(monkeypatch, tmp_path):
    entries = []
    for dataset_id, (job_id, fqn, inputs, synthetic) in DATASETS.items():
        entry = {"dataset_id": dataset_id, "description": f"{dataset_id} rows", "om_fqn": fqn}
        entry |= {"openlineage": {}, "job_id": job_id, "owner": "platform", "tags": []}
        if dataset_id.startswith("raw/"):
            entry |= {"natural_key": ["id"], "synthetic_source": synthetic}
        entries.append(entry)
        job = tmp_path / "jobs" / job_id / "job.py"
        job.parent.mkdir(parents=True, exist_ok=True)
        job.write_text(f"INPUTS = {inputs!r}\nOUTPUTS = [{dataset_id!r}]\n")
        schema = tmp_path / "schemas" / f"{dataset_id}.yml"
        schema.parent.mkdir(parents=True, exist_ok=True)
        contract = {"schema_version": "1.0.0", "columns": [{"name": c, "type": "int"} for c in COLUMNS]}
        schema.write_text(yaml.safe_dump(contract))
    (tmp_path / "datasets").mkdir()
    (tmp_path / "datasets" / "platform.yml").write_text(yaml.safe_dump({"datasets": entries}))
    (tmp_path / "glossary").mkdir()
    (tmp_path / "glossary" / "campaign.yml").write_text(yaml.safe_dump({"terms": TERMS}))
    monkeypatch.setenv("FABRIC_CONTRACTS_DIR", str(tmp_path))
    monkeypatch.setenv("FABRIC_GOVERNANCE_DIR", str(tmp_path))
    monkeypatch.setenv("FABRIC_JOBS_DIR", str(tmp_path / "jobs"))
    return tmp_path


@pytest.fixture
def offline(files, monkeypatch):
    monkeypatch.setenv("FABRIC_CONTROL_MODE", "offline")

    def fail(*args, **kwargs):
        raise AssertionError("service called in offline mode")

    for name in ("test_results", "lineage_edges", "call"):
        monkeypatch.setattr(openmetadata, name, fail)
    monkeypatch.setattr(postgres, "last_success", fail)


REFRESHED = datetime(2026, 10, 5, 9, 30, tzinfo=UTC)


@pytest.fixture
def online(files, monkeypatch):
    monkeypatch.setenv("FABRIC_CONTROL_MODE", "online")
    monkeypatch.setattr(postgres, "last_success", lambda: {"ingest/sales": (REFRESHED, 7)})
    quality = {
        "lake_raw.default.lake.lines": [("not_null", "critical", True), ("range", "warning", True)],
        "lake_unified.default.lake.orders": [("unique", "critical", False)],
        "lake_other.default.lake.unknown": [("x", "critical", False)],
    }
    monkeypatch.setattr(openmetadata, "test_results", lambda: quality)


def test_offline_catalog_from_files(offline):
    items = {i["dataset_id"]: i for i in fc.catalog()}
    assert list(items) == sorted(DATASETS)
    overview = items["mart_campaign.overview"]
    assert overview["layer"] == "mart"
    assert overview["description"] == "mart_campaign.overview rows"
    assert overview["owner"] == "platform"
    assert overview["sources"] == ["campaign", "sales"]
    assert (overview["refreshed_at"], overview["version"]) == (None, None)
    assert (overview["score"], overview["status"]) == (None, fc.NOT_MEASURED)


def test_provenance_propagates_through_lineage(offline):
    provenance = {i["dataset_id"]: i["provenance"] for i in fc.catalog()}
    assert provenance == {
        "raw/sales/lines": "original",
        "raw/campaign/attribution": "synthetic",
        "unified/orders": "original",
        "unified/attribution": "synthetic",
        "mart_campaign.overview": "synthetic",
    }


def test_catalog_filter(offline):
    assert [i["dataset_id"] for i in fc.catalog({"layer": "unified"})] == ["unified/attribution", "unified/orders"]


def test_offline_latest_score_not_measured(offline):
    assert fc.latest_score("raw/sales/lines") == fc.NOT_MEASURED


def test_latest_score_rejects_unregistered_dataset(offline):
    with pytest.raises(KeyError):
        fc.latest_score("raw/unknown/x")


def test_offline_lineage_from_job_inputs(offline):
    graph = fc.lineage("mart_campaign.overview", depth=2)
    assert {n["dataset_id"] for n in graph["nodes"]} == set(DATASETS)
    assert {"from": "raw/sales/lines", "to": "unified/orders", "job_id": "unified/orders"} in graph["edges"]
    assert {"from": "unified/orders", "to": "mart_campaign.overview", "job_id": "marts/campaign/overview"} in (
        graph["edges"]
    )


def test_lineage_depth_and_downstream(offline):
    graph = fc.lineage("unified/orders", depth=1)
    assert [(e["from"], e["to"]) for e in graph["edges"]] == [
        ("raw/sales/lines", "unified/orders"),
        ("unified/orders", "mart_campaign.overview"),
    ]


def test_term_with_dataset_metadata(offline):
    term = fc.term("attributed_orders")
    assert term["term_id"] == "attributed_orders"
    assert term["display_name"] == "Attributed Orders"
    assert term["formula"] == "count(distinct canonical_order_id)"
    assert term["notes"] == ["attributed_not_incremental"]
    assert (term["provenance"], term["synthetic"]) == ("synthetic", True)
    assert term["status"] == fc.NOT_MEASURED
    assert not [key for key in term if key.startswith("_")]
    assert fc.term("attributed_value_per_spend_ratio")["synthetic"] is False


def test_missing_term(offline):
    assert fc.term("nope") is None


def test_search_datasets_and_terms(offline):
    hits = fc.search("Attributed Value / Spend Ratio")
    assert [(h["kind"], h["id"]) for h in hits] == [("term", "attributed_value_per_spend_ratio")]
    assert {h["id"] for h in fc.search("ATTRIBUTION")} == {"raw/campaign/attribution", "unified/attribution"}
    assert fc.search("roas")[0]["name"] == "Attributed Value / Spend Ratio"
    assert fc.search("  ") == []
    assert fc.search("no such thing") == []


def test_online_quality_and_refresh_keyed_by_dataset(online):
    items = {i["dataset_id"]: i for i in fc.catalog()}
    assert (items["raw/sales/lines"]["score"], items["raw/sales/lines"]["status"]) == (100.0, "Green")
    assert (items["raw/sales/lines"]["refreshed_at"], items["raw/sales/lines"]["version"]) == (REFRESHED, 7)
    assert items["unified/orders"]["status"] == "Red"
    assert items["unified/attribution"]["status"] == fc.NOT_MEASURED
    assert fc.latest_score("unified/orders") == (0.0, "Red")


def test_online_lineage_translates_fqns(online, monkeypatch):
    edges = [
        ("lake_raw.default.lake.lines", "lake_unified.default.lake.orders", "unified/orders"),
        ("lake_unified.default.lake.orders", "serving.serving.mart_campaign.overview", None),
        ("lake_other.default.lake.unknown", "lake_unified.default.lake.orders", "x"),
    ]
    calls = []
    monkeypatch.setattr(openmetadata, "lineage_edges", lambda fqn, depth: calls.append((fqn, depth)) or edges)
    graph = fc.lineage("unified/orders", depth=3)
    assert calls == [("lake_unified.default.lake.orders", 3)]
    assert graph["edges"] == [
        {"from": "raw/sales/lines", "to": "unified/orders", "job_id": "unified/orders"},
        {"from": "unified/orders", "to": "mart_campaign.overview", "job_id": None},
    ]
    assert [n["dataset_id"] for n in graph["nodes"]] == ["mart_campaign.overview", "raw/sales/lines", "unified/orders"]


def test_online_degrades_when_services_down(online, monkeypatch):
    def down(*args):
        raise HttpError("GET", "om", 503, "down")

    def refused():
        raise ConnectionRefusedError("pg down")

    monkeypatch.setattr(openmetadata, "test_results", down)
    monkeypatch.setattr(openmetadata, "lineage_edges", down)
    monkeypatch.setattr(postgres, "last_success", refused)
    assert fc.latest_score("raw/sales/lines") == fc.NOT_MEASURED
    graph = fc.lineage("unified/orders")
    assert ("raw/sales/lines", "unified/orders") in {(e["from"], e["to"]) for e in graph["edges"]}


def test_online_term_carries_dataset_quality(online):
    term = fc.term("attributed_value_per_spend_ratio")
    assert (term["score"], term["status"]) == (0.0, "Red")


def test_repo_provenance_matches_glossary_closure(monkeypatch):
    monkeypatch.setenv("FABRIC_CONTROL_MODE", "offline")
    synthetic = {i["dataset_id"] for i in fc.catalog({"provenance": "synthetic"})}
    assert synthetic == synthetic_closure()


def test_repo_raw_datasets_have_descriptions(monkeypatch):
    monkeypatch.setenv("FABRIC_CONTROL_MODE", "offline")
    raw = fc.catalog({"layer": "raw"})
    assert raw and all(i["description"] and i["owner"] for i in raw)
