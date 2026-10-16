from app.pages.governance import access_matrix, data_quality
from app.shell import PageSpec

PAGES = [
    PageSpec(
        key="data_quality",
        title="Data Quality & Exceptions",
        group="Data trust",
        render=data_quality.render,
        roles=frozenset({"UG05"}),
        home_for=frozenset({"UG05"}),
        icon=":material/verified:",
    ),
    PageSpec(
        key="access_matrix",
        title="Access Matrix",
        group="Data trust",
        render=access_matrix.render,
        roles=frozenset({"UG05"}),
        icon=":material/admin_panel_settings:",
    ),
]
