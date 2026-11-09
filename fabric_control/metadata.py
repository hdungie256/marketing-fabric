from typing import Any

from fabric_control.clients import openmetadata
from fabric_control.clients.http import HttpError
from fabric_control.config import log, mode, stub
from fabric_control.contracts import columns, load_schema
from fabric_control.glossary import GLOSSARY_NAME, labelled_terms, load_tags
from fabric_control.registry import load_registry


def _describe_term(term_id: str, term: dict[str, Any]) -> str:
    registry = load_registry()
    lines = [
        term["definition"],
        "",
        f"Formula: {term['formula']}",
        f"Source: {', '.join(term['dataset_id'] + '.' + c for c in term['source_columns'])}"
        f" ({registry[term['dataset_id']]['om_fqn']})",
        f"Rules: {', '.join(term['rules'])}",
        f"Owner slice: {term['owner_slice']}",
        f"Provenance: {term['provenance']}",
    ]
    lines += ["", "Limitations:"] + [f"- {item}" for item in term["limitations"]]
    lines += ["", "Notes:"] + [f"- {item}" for item in term["notes"]]
    return "\n".join(lines)


def sync_glossary() -> None:
    terms = labelled_terms()
    if mode() == "offline":
        stub("sync_glossary", terms=sorted(terms))
        return
    try:
        openmetadata.put_glossary(
            GLOSSARY_NAME,
            "Marketing Metrics",
            "Single source of truth for marketing metric definitions (FR-11). Managed as code; do not edit in UI.",
        )
        for term_id, term in terms.items():
            openmetadata.put_glossary_term(GLOSSARY_NAME, term_id, term["display_name"], _describe_term(term_id, term))
    except (HttpError, OSError) as e:
        log.warning("glossary sync to OpenMetadata failed: %s", e)


def sync_tags() -> None:
    tags = load_tags()
    if mode() == "offline":
        stub("sync_tags", tags=len(tags))
        return
    try:
        for classification in sorted({c for c, _ in tags}):
            openmetadata.put_classification(classification, f"Fabric classification {classification}, managed as code.")
        for (classification, name), tag in tags.items():
            openmetadata.put_tag(classification, name, tag["description"])
    except (HttpError, OSError) as e:
        log.warning("tag sync to OpenMetadata failed: %s", e)


def emit_lineage(job_id: str, inputs: list[str], outputs: list[str]) -> None:
    if mode() == "offline":
        stub("emit_lineage", job_id=job_id, inputs=inputs, outputs=outputs)
        return
    registry = load_registry()
    fqns = {dataset_id: registry[dataset_id]["om_fqn"] for dataset_id in [*inputs, *outputs]}
    try:
        pipeline_id = openmetadata.put_pipeline(job_id)
        ids = {dataset_id: openmetadata.table_id(fqn) for dataset_id, fqn in fqns.items()}
        for source in inputs:
            for target in outputs:
                openmetadata.add_lineage(ids[source], ids[target], pipeline_id)
    except (HttpError, OSError) as e:
        log.warning("lineage for %s not recorded: %s", job_id, e)


RAW_COLUMNS = [
    ("_load_id", "string"),
    ("_ingested_at", "timestamp"),
    ("_source", "string"),
    ("_load_kind", "string"),
    ("_source_version", "bigint"),
    ("_schema_version", "string"),
    ("_run_id", "string"),
]
DELTA_COLUMNS = [("_run_id", "string")]


def delta_columns(dataset_id: str) -> list[tuple[str, str]]:
    extra = RAW_COLUMNS if dataset_id.startswith("raw/") else DELTA_COLUMNS
    return columns(load_schema(dataset_id)) + extra


def register(dataset_id: str) -> None:
    if mode() == "offline":
        stub("register", dataset_id=dataset_id)
        return
    openmetadata.put_table(load_registry()[dataset_id]["om_fqn"], delta_columns(dataset_id))


def register_all() -> list[str]:
    datasets = [d for d, entry in load_registry().items() if entry["om_fqn"].startswith("lake_")]
    for dataset_id in datasets:
        register(dataset_id)
    return datasets
