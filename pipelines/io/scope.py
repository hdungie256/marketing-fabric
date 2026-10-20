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


def restrict(scope: Scope | None, columns: list[str]) -> Scope:
    if not scope or scope.get("mode") != "scope":
        return {"mode": "full"}
    keys = {c: v for c, v in scope["keys"].items() if c in columns}
    return {"mode": "scope", "keys": keys} if keys else {"mode": "full"}


def narrow(df, scope: Scope | None, columns: list[str] | None = None):
    scoped = restrict(scope, columns if columns is not None else df.columns)
    predicate = scope_predicate(scoped)
    return df.filter(predicate) if predicate else df
