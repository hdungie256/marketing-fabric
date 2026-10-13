from app.pages.governance import access_matrix
from app.shell import PageSpec

PAGES = [
    PageSpec(
        key="access_matrix",
        title="Access Matrix",
        group="Data trust",
        render=access_matrix.render,
        roles=frozenset({"UG05"}),
        icon=":material/admin_panel_settings:",
    ),
]
