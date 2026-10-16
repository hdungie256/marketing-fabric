from app.pages.catalog import catalog_glossary, lineage
from app.shell import PageSpec
from app.shell.roles import ROLES

ALL = frozenset(ROLES)

PAGES = [
    PageSpec(
        key="lineage",
        title="Lineage",
        group="Data trust",
        render=lineage.render,
        roles=ALL,
        icon=":material/account_tree:",
    ),
    PageSpec(
        key="catalog_glossary",
        title="Catalog & Glossary",
        group="Data trust",
        render=catalog_glossary.render,
        roles=ALL,
        icon=":material/menu_book:",
    ),
]
