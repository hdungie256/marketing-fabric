import pytest

from fabric_control.policy import load_policy

ROLES = ["UG01", "UG02", "UG03", "UG04", "UG05", "UG06"]
# FR-20: UG04 sees SKU cost of goods, UG03 only the aggregate, UG01 no cost of goods;
# customer identifiers are masked for every role without a CRM need.
EXPECTED = {
    "Finance.sku_cost": {"UG04": "allow"},
    "Finance.aggregate": {"UG03": "allow", "UG04": "allow"},
    "Sensitivity.direct_identifier": {"UG02": "allow"},
}
FALLBACK = {"Finance.sku_cost": "deny", "Finance.aggregate": "deny", "Sensitivity.direct_identifier": "mask:partial"}


def action(policy, tag: str, role: str) -> str:
    actions = policy.actions[tag]
    return actions.get(role, actions.get("default", "deny"))


@pytest.mark.parametrize("tag", EXPECTED)
@pytest.mark.parametrize("role", ROLES)
def test_tag_actions_match_fr20(tag, role):
    assert action(load_policy(), tag, role) == EXPECTED[tag].get(role, FALLBACK[tag])


def test_customer_id_columns_are_identifiers():
    policy = load_policy()
    for dataset_id, columns in policy.column_tags.items():
        if "customer_id" in columns:
            assert columns["customer_id"] == "Sensitivity.direct_identifier", dataset_id
