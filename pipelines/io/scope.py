from typing import Any

Scope = dict[str, Any]


def literal(value: Any) -> str:
    if isinstance(value, bool):
        return str(value).lower()
    if isinstance(value, int | float):
        return str(value)
    return "'" + str(value).replace("'", "''") + "'"


def scope_predicate(scope: Scope | None) -> str | None:
    if not scope or scope.get("mode") == "full":
        return None
    keys = scope.get("keys") or {}
    if scope.get("mode") != "scope" or not keys:
        raise ValueError(f"invalid scope {scope}")
    parts = []
    for column, values in keys.items():
        if not values:
            raise ValueError(f"empty scope values for {column}")
        parts.append(f"`{column}` IN ({', '.join(literal(v) for v in values)})")
    return " AND ".join(parts)
