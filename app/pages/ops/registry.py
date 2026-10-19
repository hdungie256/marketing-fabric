from app.pages.ops import pipeline_status
from app.shell import PageSpec

PAGES = [
    PageSpec(
        key="pipeline_status",
        title="Pipeline Status",
        group="Operations",
        render=pipeline_status.render,
        roles=frozenset({"UG06"}),
        home_for=frozenset({"UG06"}),
        icon=":material/monitoring:",
    ),
]
