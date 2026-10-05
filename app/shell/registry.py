import importlib
import re
from collections.abc import Callable, Sequence
from dataclasses import dataclass

from app.shell.roles import ROLES

GROUPS = ("Campaigns", "Customers", "Finance", "Data trust", "Operations")
SLICES = ("campaign", "customer", "finance", "catalog", "governance", "ops", "changes")
_KEY = re.compile(r"^[a-z0-9_]+$")


class RegistryError(ValueError):
    pass


@dataclass(frozen=True)
class PageSpec:
    key: str
    title: str
    group: str
    render: Callable[[], None]
    roles: frozenset[str]
    home_for: frozenset[str] = frozenset()
    icon: str | None = None


def load_pages(slices: Sequence[str] = SLICES) -> list[PageSpec]:
    pages: list[PageSpec] = []
    for name in slices:
        pages.extend(importlib.import_module(f"app.pages.{name}.registry").PAGES)
    return pages


def validate(pages: Sequence[PageSpec]) -> None:
    errors: list[str] = []
    seen: set[str] = set()
    homes: dict[str, list[str]] = {}
    for p in pages:
        if not _KEY.match(p.key):
            errors.append(f"{p.key}: key must match [a-z0-9_]+")
        if p.key in seen:
            errors.append(f"{p.key}: duplicate key")
        seen.add(p.key)
        if p.group not in GROUPS:
            errors.append(f"{p.key}: unknown group {p.group!r}")
        if not p.roles:
            errors.append(f"{p.key}: no roles")
        unknown = sorted(p.roles - ROLES.keys())
        if unknown:
            errors.append(f"{p.key}: unknown roles {unknown}")
        if not p.home_for <= p.roles:
            errors.append(f"{p.key}: home_for not in roles")
        for code in p.home_for:
            homes.setdefault(code, []).append(p.key)
    for code, keys in sorted(homes.items()):
        if len(keys) > 1:
            errors.append(f"{code}: more than one home ({', '.join(keys)})")
    if errors:
        raise RegistryError("; ".join(errors))
