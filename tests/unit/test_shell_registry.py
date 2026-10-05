import pytest

from app.shell.registry import GROUPS, SLICES, PageSpec, RegistryError, load_pages, validate


def page(key="campaign_overview", group="Campaigns", roles=("UG01",), home_for=()):
    return PageSpec(key, key.title(), group, lambda: None, frozenset(roles), frozenset(home_for))


def test_groups_and_slice_order_are_fixed():
    assert GROUPS == ("Campaigns", "Customers", "Finance", "Data trust", "Operations")
    assert SLICES == ("campaign", "customer", "finance", "catalog", "governance", "ops", "changes")


def test_load_pages_reads_every_slice_registry():
    assert isinstance(load_pages(), list)


def test_valid_pages_pass():
    validate([page(home_for=("UG01",)), page("targets", roles=("UG03",), home_for=("UG03",))])


@pytest.mark.parametrize(
    "pages,message",
    [
        ([page("Campaign-Overview")], "key must match"),
        ([page(), page()], "duplicate key"),
        ([page(group="Marketing")], "unknown group"),
        ([page(roles=())], "no roles"),
        ([page(roles=("UG01", "UG09"))], "unknown roles ['UG09']"),
        ([page(home_for=("UG03",))], "home_for not in roles"),
        ([page(home_for=("UG01",)), page("other", home_for=("UG01",))], "UG01: more than one home"),
    ],
)
def test_invalid_pages_raise_with_reason(pages, message):
    with pytest.raises(RegistryError, match=message.replace("[", r"\[").replace("]", r"\]")):
        validate(pages)


def test_missing_home_is_allowed():
    validate([page()])
