from app.pages.campaign import new_returning, overview, products
from app.pages.campaign.placeholder import placeholder
from app.shell import PageSpec

PAGES = [
    PageSpec(
        key="campaign_overview",
        title="Campaign Overview",
        group="Campaigns",
        render=overview.render,
        roles=frozenset({"UG01", "UG03"}),
        home_for=frozenset({"UG01"}),
        icon=":material/campaign:",
    ),
    PageSpec(
        key="campaign_comparison",
        title="Campaign Comparison",
        group="Campaigns",
        render=placeholder("4.1"),
        roles=frozenset({"UG01", "UG03"}),
        icon=":material/compare_arrows:",
    ),
    PageSpec(
        key="targets",
        title="Targets",
        group="Campaigns",
        render=placeholder("4.4"),
        roles=frozenset({"UG03"}),
        home_for=frozenset({"UG03"}),
        icon=":material/flag:",
    ),
    PageSpec(
        key="products_categories",
        title="Products & Categories",
        group="Campaigns",
        render=products.render,
        roles=frozenset({"UG01"}),
        icon=":material/category:",
    ),
    PageSpec(
        key="new_vs_returning",
        title="New vs Returning",
        group="Campaigns",
        render=new_returning.render,
        roles=frozenset({"UG01", "UG02"}),
        icon=":material/group:",
    ),
]
