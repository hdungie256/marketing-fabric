from collections.abc import Callable
from dataclasses import dataclass


@dataclass(frozen=True)
class PageSpec:
    key: str
    title: str
    group: str
    render: Callable[[], None]
    roles: frozenset[str]
    home_for: frozenset[str] = frozenset()
    icon: str | None = None
