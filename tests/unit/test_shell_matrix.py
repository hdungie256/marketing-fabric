from app.shell.navigation import home_for
from app.shell.registry import load_pages, validate
from app.shell.roles import ROLES
from tests.unit.shell_matrix import EXPERIENCE_MATRIX, full_registry


def test_full_matrix_gives_every_role_exactly_one_home():
    pages = full_registry()
    validate(pages)
    homes = {code: home_for(code, pages).key for code in ROLES}
    assert homes == {
        "UG01": "campaign_overview",
        "UG02": "rfm_segments",
        "UG03": "targets",
        "UG04": "budget_spend",
        "UG05": "data_quality",
        "UG06": "pipeline_status",
    }


def test_real_registries_are_valid():
    validate(load_pages())


def test_real_registries_match_experience_matrix():
    for page in load_pages():
        assert page.key in EXPERIENCE_MATRIX, f"{page.key}: not a page in EXPERIENCE.md"
        title, group, roles, homes = EXPERIENCE_MATRIX[page.key]
        assert (page.title, page.group, set(page.roles), set(page.home_for)) == (title, group, roles, homes), page.key


def test_p2_placeholders_are_registered():
    keys = {p.key for p in load_pages()}
    assert {
        "campaign_overview",
        "campaign_comparison",
        "targets",
        "products_categories",
        "new_vs_returning",
        "change_history",
    } <= keys
