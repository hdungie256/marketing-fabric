"""Role × page matrix copied from docs/03-ux-design/EXPERIENCE.md (Information Architecture)."""

ALL = frozenset({"UG01", "UG02", "UG03", "UG04", "UG05", "UG06"})

# key: (title, group, roles, home_for)
EXPERIENCE_MATRIX = {
    "campaign_overview": ("Campaign Overview", "Campaigns", {"UG01", "UG03"}, {"UG01"}),
    "campaign_comparison": ("Campaign Comparison", "Campaigns", {"UG01", "UG03"}, set()),
    "targets": ("Targets", "Campaigns", {"UG03"}, {"UG03"}),
    "products_categories": ("Products & Categories", "Campaigns", {"UG01"}, set()),
    "new_vs_returning": ("New vs Returning", "Campaigns", {"UG01", "UG02"}, set()),
    "rfm_segments": ("RFM Segments", "Customers", {"UG02"}, {"UG02"}),
    "audience_builder": ("Audience Builder", "Customers", {"UG01", "UG02"}, set()),
    "win_back": ("Win-back", "Customers", {"UG02"}, set()),
    "budget_spend": ("Budget & Spend", "Finance", {"UG03", "UG04"}, {"UG04"}),
    "contribution": ("Contribution", "Finance", {"UG03", "UG04"}, set()),
    "catalog_glossary": ("Catalog & Glossary", "Data trust", set(ALL), set()),
    "lineage": ("Lineage", "Data trust", set(ALL), set()),
    "data_quality": ("Data Quality & Exceptions", "Data trust", {"UG05"}, {"UG05"}),
    "access_matrix": ("Access Matrix", "Data trust", {"UG05"}, set()),
    "pipeline_status": ("Pipeline Status", "Operations", {"UG06"}, {"UG06"}),
    "change_history": ("Change History", "Operations", {"UG01", "UG03", "UG04", "UG06"}, set()),
}


def full_registry(render_for=None):
    from app.shell.registry import PageSpec

    render_for = render_for or {}
    return [
        PageSpec(key, title, group, render_for.get(key, lambda: None), frozenset(roles), frozenset(homes))
        for key, (title, group, roles, homes) in EXPERIENCE_MATRIX.items()
    ]
