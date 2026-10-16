"""Lineage page (Story 2.3, FR-15). Visible to all roles."""

from __future__ import annotations

import fabric_control
from app.shell import Filter, filter_bar
from app.shell.components.lineage_graph import lineage_graph

KEY = "lineage"


def render() -> None:
    ids = sorted(entry["dataset_id"] for entry in fabric_control.catalog())
    if not ids:
        return
    default = "mart_campaign.campaign_overview" if "mart_campaign.campaign_overview" in ids else ids[0]
    values = filter_bar(
        KEY,
        [
            Filter("dataset", "Dataset", ids, default=default),
            Filter("depth", "Depth", [1, 2, 3], default=1),
        ],
    )
    lineage_graph(values["dataset"], values["depth"], key=KEY)
