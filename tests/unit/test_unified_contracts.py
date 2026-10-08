"""Story 1.6 contract tests (no Spark): registry, schemas, mapping file and job wiring."""

from pathlib import Path

from fabric_control import load_registry
from fabric_control.contracts import columns, load_schema
from pipelines.dags.job_graph import job_graph
from pipelines.jobs.unified._common import load_mapping, load_mapping_rows

ROOT = Path(__file__).resolve().parents[2]

UNIFIED = [
    "unified/orders",
    "unified/order_lines",
    "unified/customers",
    "unified/products",
    "unified/product_cost",
    "unified/ref_category_map",
]


def test_unified_datasets_registered_with_required_fields():
    registry = load_registry()
    for dataset_id in UNIFIED:
        entry = registry[dataset_id]
        assert entry["job_id"] == dataset_id
        assert entry["om_fqn"].startswith("lake_unified.")
        assert entry["openlineage"]["name"] == dataset_id
        assert entry["natural_key"], dataset_id


def test_unified_schemas_have_key_columns():
    assert "order_key" in dict(columns(load_schema("unified/orders")))
    assert "sales_line_id" in dict(columns(load_schema("unified/order_lines")))
    assert "first_observed_order_date" in dict(columns(load_schema("unified/customers")))
    assert "product_sku" in dict(columns(load_schema("unified/products")))
    assert "estimated_unit_cost" in dict(columns(load_schema("unified/product_cost")))
    assert "raw_category" in dict(columns(load_schema("unified/ref_category_map")))


def test_unified_registry_keys_match_schemas():
    for dataset_id in UNIFIED:
        names = {name for name, _ in columns(load_schema(dataset_id))}
        assert set(load_registry()[dataset_id]["natural_key"]) <= names, dataset_id


def test_category_mapping_normalizes_only_true_synonyms():
    mapping = load_mapping()
    assert mapping["Notebooks"] == "Notebooks & Journals"
    for nest in ("Nest", "Nest-USA", "Nest-Canada"):
        assert nest not in mapping, nest
    rows = load_mapping_rows()
    assert {(r["raw_category"], r["canonical_category"]) for r in rows} == {("Notebooks", "Notebooks & Journals")}


def test_unified_jobs_wired_in_graph():
    graph = job_graph(ROOT)
    assert graph["unified/orders"] == {"ingest/sales"}
    assert graph["unified/order_lines"] == {"ingest/sales"}
    assert graph["unified/customers"] == {"ingest/crm", "ingest/sales"}
    assert graph["unified/products"] == {"ingest/sales"}
    assert graph["unified/product_cost"] == {"ingest/erp"}
    assert graph["unified/ref_category_map"] == set()


def test_every_unified_job_has_dq_rules():
    for dataset_id in UNIFIED:
        slug = dataset_id.split("/")[-1]
        path = ROOT / "pipelines" / "jobs" / "unified" / slug / "data_quality" / f"{slug}.yml"
        assert path.exists(), path
