from app.shell.navigation import FALLBACK_KEY, grouped, home_for, pages_for, resolve_after_switch
from app.shell.registry import PageSpec


def page(key, group, roles, home_for=()):
    return PageSpec(key, key, group, lambda: None, frozenset(roles), frozenset(home_for))


PAGES = [
    page("campaign_overview", "Campaigns", {"UG01", "UG03"}, {"UG01"}),
    page("targets", "Campaigns", {"UG03"}, {"UG03"}),
    page("catalog_glossary", "Data trust", {"UG01", "UG03", "UG05"}),
    page("change_history", "Operations", {"UG01", "UG03"}),
]


def test_pages_for_keeps_registry_order():
    assert [p.key for p in pages_for("UG03", PAGES)] == [
        "campaign_overview",
        "targets",
        "catalog_glossary",
        "change_history",
    ]


def test_home_is_the_declared_home():
    assert home_for("UG03", PAGES).key == "targets"


def test_home_falls_back_to_first_permitted_page():
    assert home_for("UG05", PAGES).key == "catalog_glossary"


def test_home_is_none_without_pages():
    assert home_for("UG06", PAGES) is None


def test_switch_stays_on_permitted_page():
    assert resolve_after_switch("campaign_overview", "UG03", PAGES) == "campaign_overview"


def test_switch_goes_home_when_page_not_permitted():
    assert resolve_after_switch("targets", "UG01", PAGES) == "campaign_overview"


def test_switch_from_nowhere_goes_home():
    assert resolve_after_switch(None, "UG01", PAGES) == "campaign_overview"


def test_switch_to_role_without_pages_uses_fallback():
    assert resolve_after_switch("campaign_overview", "UG06", PAGES) == FALLBACK_KEY


def test_switch_from_fallback_page_goes_home():
    assert resolve_after_switch(FALLBACK_KEY, "UG01", PAGES) == "campaign_overview"


def test_grouped_follows_fixed_group_order_and_skips_empty_groups():
    groups = grouped("UG01", PAGES)
    assert list(groups) == ["Campaigns", "Data trust", "Operations"]
    assert [p.key for p in groups["Campaigns"]] == ["campaign_overview"]
