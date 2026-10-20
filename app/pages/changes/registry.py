from app.pages.changes import change_history
from app.shell import PageSpec

PAGES = [
    PageSpec(
        key="change_history",
        title="Change History",
        group="Operations",
        render=change_history.render,
        roles=frozenset({"UG01", "UG03", "UG04", "UG06"}),
        icon=":material/history:",
    ),
]
