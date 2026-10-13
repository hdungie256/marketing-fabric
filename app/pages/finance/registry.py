from app.pages.finance import budget_spend
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
]
