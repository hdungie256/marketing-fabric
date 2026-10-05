from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class Filter:
    name: str
    label: str
    options: Sequence[Any]
    default: Any = None
    format_func: Callable[[Any], str] = str


def filter_bar(page_key: str, filters: Sequence[Filter]) -> dict[str, Any]:
    raise NotImplementedError("Story 1.11")
