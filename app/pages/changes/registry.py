from app.pages.campaign.placeholder import placeholder
from app.shell import PageSpec

PAGES = [
    PageSpec(
        key="change_history",
        title="Change History",
        group="Operations",
        render=placeholder("8.6"),
        roles=frozenset({"UG01", "UG03", "UG04", "UG06"}),
        icon=":material/history:",
    ),
]
