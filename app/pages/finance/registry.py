from app.pages.finance import budget_spend, contribution
from app.shell import PageSpec

PAGES = [
    PageSpec(
        key="budget_spend",
        title="Budget & Spend",
        group="Finance",
        render=budget_spend.render,
        roles=frozenset({"UG03", "UG04"}),
        home_for=frozenset({"UG04"}),
        icon=":material/payments:",
    ),
    PageSpec(
        key="contribution",
        title="Contribution",
        group="Finance",
        render=contribution.render,
        roles=frozenset({"UG03", "UG04"}),
        icon=":material/account_balance:",
    ),
]
