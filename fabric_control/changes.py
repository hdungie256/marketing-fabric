from typing import Any

from fabric_control.glossary import load_terms
from fabric_control.manifests import load_manifests
from fabric_control.policy import ALLOW, load_policy

LOG = "ops.metric_change_log"


def term_for(dataset_id: str, column: str, terms: dict[str, dict[str, Any]]) -> str:
    for term_id, term in terms.items():
        if term["dataset_id"] == dataset_id and term["column"] == column:
            return term_id
    return column


def visible(dataset_id: str, columns: list[str]) -> list[str]:
    policy = load_policy()
    readers = policy.readers.get(LOG, [])
    tagged = policy.column_tags.get(dataset_id, {})
    return [c for c in columns if c in tagged and all(policy.tag_action(r, dataset_id, c) == ALLOW for r in readers)]


def diff(
    grain: list[str], metrics: list[str], before: list[dict[str, Any]], after: list[dict[str, Any]]
) -> list[tuple[dict[str, str], str, Any, Any]]:
    def key(row: dict[str, Any]) -> tuple[str, ...]:
        return tuple(str(row[c]) for c in grain)

    old, new = {key(r): r for r in before}, {key(r): r for r in after}
    changes = []
    for k in sorted(old.keys() | new.keys()):
        for metric in metrics:
            was, now = old.get(k, {}).get(metric), new.get(k, {}).get(metric)
            if was != now:
                changes.append((dict(zip(grain, k, strict=True)), metric, was, now))
    return changes


def metric_changes(
    dataset_id: str, before: list[dict[str, Any]], after: list[dict[str, Any]]
) -> list[tuple[dict[str, str], str, Any, Any]]:
    manifest = load_manifests()[dataset_id]
    terms = load_terms()
    metrics = visible(dataset_id, manifest.get("metrics") or [])
    return [
        (grain_key, term_for(dataset_id, metric, terms), was, now)
        for grain_key, metric, was, now in diff(manifest["grain"], metrics, before, after)
    ]
