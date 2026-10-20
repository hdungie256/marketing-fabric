from app.pages.customer import audience_builder, rfm_segments, win_back
from app.shell import PageSpec

PAGES = [
    PageSpec(
        key="rfm_segments",
        title="RFM Segments",
        group="Customers",
        render=rfm_segments.render,
        roles=frozenset({"UG02"}),
        home_for=frozenset({"UG02"}),
        icon=":material/group:",
    ),
    PageSpec(
        key="audience_builder",
        title="Audience Builder",
        group="Customers",
        render=audience_builder.render,
        roles=frozenset({"UG01", "UG02"}),
        icon=":material/groups:",
    ),
    PageSpec(
        key="win_back",
        title="Win-back",
        group="Customers",
        render=win_back.render,
        roles=frozenset({"UG02"}),
        icon=":material/history:",
    ),
]
