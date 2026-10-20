from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from fabric_control.clients import postgres
from fabric_control.config import log, mode, stub
from fabric_control.glossary import governance_dir, load_tags

GENERATED = "generated-by sync_policies"
VIEW_SUFFIX = "_v"
DENIED_SUFFIX = "__denied"
DEFAULT = "default"
ALLOW = "allow"
DENY = "deny"
MASK = "mask:"
WRITERS = {"app": "app_writer", "ops": "ops_writer"}
MASKS = {
    "partial": (
        "CASE WHEN length(value) > 3 THEN left(value, 1) || '****' || right(value, 2) ELSE '****' END",
        r"^(.\*{4}.{2}|\*{4})$",
    )
}


class PolicyError(Exception):
    pass


def quote(name: str) -> str:
    return '"' + name.replace('"', '""') + '"'


def literal(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


def qualified(schema: str, name: str) -> str:
    return f"{quote(schema)}.{quote(name)}"


def view_name(dataset_id: str) -> tuple[str, str]:
    schema, table = dataset_id.split(".", 1)
    return schema + VIEW_SUFFIX, table


def mask_function(action: str) -> str:
    return f"policy_mask_{action.removeprefix(MASK)}"


@dataclass(frozen=True)
class Policy:
    roles: dict[str, str]
    readers: dict[str, list[str]]
    actions: dict[str, dict[str, str]]
    column_tags: dict[str, dict[str, str]]
    editors: dict[str, list[str]] = field(default_factory=dict)

    def tag_action(self, role: str, dataset_id: str, column: str) -> str:
        actions = self.actions[self.column_tags[dataset_id][column]]
        return actions.get(role, actions.get(DEFAULT, DENY))

    def action(self, role: str, dataset_id: str, column: str) -> str:
        if role not in self.readers.get(dataset_id, []):
            return DENY
        return self.tag_action(role, dataset_id, column)

    def check(self, tables: dict[str, list[str]]) -> None:
        untagged = [
            f"{dataset_id}.{column}"
            for dataset_id, columns in tables.items()
            for column in columns
            if column not in self.column_tags.get(dataset_id, {})
        ]
        if untagged:
            raise PolicyError(f"untagged serving columns: {', '.join(untagged)}")
        unknown = sorted(set(self.readers) - set(tables))
        if unknown:
            raise PolicyError(f"access_matrix.yml grants unknown datasets: {', '.join(unknown)}")

    def effective(self, tables: dict[str, list[str]]) -> list[tuple[str, str, str, str]]:
        return [
            (role, dataset_id, column, self.action(role, dataset_id, column))
            for role in self.roles
            for dataset_id, columns in tables.items()
            for column in columns
        ]


def valid_action(action: Any) -> bool:
    if action in (ALLOW, DENY):
        return True
    return isinstance(action, str) and action.startswith(MASK) and action.removeprefix(MASK) in MASKS


def load_policy(directory: Path | None = None) -> Policy:
    base = directory or governance_dir()
    matrix = yaml.safe_load((base / "access_matrix.yml").read_text()) or {}
    roles = matrix.get("roles") or {}
    readers = matrix.get("read") or {}
    editors = matrix.get("edit") or {}
    for dataset_id, codes in [*readers.items(), *editors.items()]:
        unknown = sorted(set(codes) - set(roles))
        if unknown:
            raise PolicyError(f"access_matrix.yml: {dataset_id} lists unknown roles {unknown}")
    actions: dict[str, dict[str, str]] = {}
    for (classification, name), tag in load_tags(base).items():
        tag_actions = tag.get("actions") or {}
        for key, action in tag_actions.items():
            if key != DEFAULT and key not in roles:
                raise PolicyError(f"{tag['_file']}: tag {classification}.{name} has unknown role {key}")
            if not valid_action(action):
                raise PolicyError(f"{tag['_file']}: tag {classification}.{name} has invalid action {action!r}")
        actions[f"{classification}.{name}"] = tag_actions
    column_tags: dict[str, dict[str, str]] = {}
    origins: dict[str, str] = {}
    for path in sorted((base / "tags").glob("*.yml")):
        for dataset_id, columns in ((yaml.safe_load(path.read_text()) or {}).get("columns") or {}).items():
            if dataset_id in column_tags:
                raise PolicyError(f"columns of {dataset_id} tagged in {origins[dataset_id]} and {path.name}")
            for column, tag in columns.items():
                if tag not in actions:
                    raise PolicyError(f"{path.name}: {dataset_id}.{column} uses unknown tag {tag!r}")
            column_tags[dataset_id] = columns
            origins[dataset_id] = path.name
    return Policy(roles, readers, actions, column_tags, editors)


def logins(names: list[str]) -> str:
    return ", ".join(literal(name) for name in names)


def column_sql(policy: Policy, dataset_id: str, column: str) -> list[str]:
    by_action: dict[str, list[str]] = {}
    for role, login in policy.roles.items():
        by_action.setdefault(policy.tag_action(role, dataset_id, column), []).append(login)
    name = quote(column)
    if set(by_action) == {ALLOW}:
        return [name]
    schema = quote(view_name(dataset_id)[0])
    masked = any(action.startswith(MASK) for action in by_action)
    plain = f"{name}::text" if masked else name
    branches = []
    for action, names in sorted(by_action.items()):
        if action == DENY:
            continue
        value = plain if action == ALLOW else f"{schema}.{mask_function(action)}({name}::text)"
        branches.append(f"WHEN current_user IN ({logins(names)}) THEN {value}")
    result = [f"CASE {' '.join(branches) or f'WHEN false THEN {name}'} END AS {name}"]
    if DENY in by_action:
        visible = [login for action, names in by_action.items() if action != DENY for login in names]
        flag = f"current_user NOT IN ({logins(visible)})" if visible else "true"
        result.append(f"{flag} AS {quote(column + DENIED_SUFFIX)}")
    return result


def view_sql(policy: Policy, dataset_id: str, columns: list[str]) -> str:
    schema, table = dataset_id.split(".", 1)
    select = ", ".join(part for column in columns for part in column_sql(policy, dataset_id, column))
    return f"CREATE VIEW {qualified(*view_name(dataset_id))} AS SELECT {select} FROM {qualified(schema, table)}"


def masks_used(policy: Policy, dataset_ids: list[str]) -> list[str]:
    used = {
        action
        for dataset_id in dataset_ids
        for tag in policy.column_tags[dataset_id].values()
        for action in policy.actions[tag].values()
        if action.startswith(MASK)
    }
    return sorted(used)


def statements(policy: Policy, tables: dict[str, list[str]]) -> list[str]:
    policy.check(tables)
    comment = literal(GENERATED)
    role_logins = ", ".join(quote(login) for login in policy.roles.values())
    schemas: dict[str, list[str]] = {}
    for dataset_id in tables:
        schemas.setdefault(dataset_id.split(".", 1)[0], []).append(dataset_id)
    result = []
    for schema, dataset_ids in sorted(schemas.items()):
        target = quote(schema + VIEW_SUFFIX)
        result += [f"CREATE SCHEMA {target}", f"COMMENT ON SCHEMA {target} IS {comment}"]
        for action in masks_used(policy, dataset_ids):
            function = f"{target}.{mask_function(action)}"
            body = MASKS[action.removeprefix(MASK)][0]
            result += [
                f"CREATE FUNCTION {function}(value text) RETURNS text LANGUAGE sql IMMUTABLE STRICT "
                f"AS $$ SELECT {body} $$",
                f"COMMENT ON FUNCTION {function}(text) IS {comment}",
            ]
        result += [
            f"REVOKE ALL ON SCHEMA {quote(schema)} FROM {role_logins}",
            f"REVOKE ALL ON ALL TABLES IN SCHEMA {quote(schema)} FROM {role_logins}",
        ]
        granted: set[str] = set()
        for dataset_id in dataset_ids:
            view = qualified(*view_name(dataset_id))
            result += [view_sql(policy, dataset_id, tables[dataset_id]), f"COMMENT ON VIEW {view} IS {comment}"]
            readers = [policy.roles[role] for role in policy.readers.get(dataset_id, [])]
            if readers:
                result.append(f"GRANT SELECT ON {view} TO {', '.join(quote(login) for login in readers)}")
                granted.update(readers)
        if granted:
            result.append(f"GRANT USAGE ON SCHEMA {target} TO {', '.join(quote(login) for login in sorted(granted))}")
        writer = WRITERS.get(schema)
        if writer:
            result += [
                f"GRANT USAGE ON SCHEMA {quote(schema)} TO {quote(writer)}",
                f"GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA {quote(schema)} TO {quote(writer)}",
                f"GRANT USAGE ON ALL SEQUENCES IN SCHEMA {quote(schema)} TO {quote(writer)}",
            ]
    return result


def sync_policies() -> None:
    if mode() == "offline":
        stub("sync_policies")
        return
    policy = load_policy()
    with postgres.connect() as conn:
        missing = postgres.missing_roles(conn, [*policy.roles.values(), *WRITERS.values()])
        if missing:
            raise PolicyError(f"database logins missing: {', '.join(missing)}; run compose/pg-init/roles.sh")
        with conn.transaction():
            tables = postgres.serving_tables(conn)
            generated = statements(policy, tables)
            comments = postgres.schema_comments(conn)
            targets = {dataset_id.split(".", 1)[0] + VIEW_SUFFIX for dataset_id in tables}
            foreign = sorted(s for s in targets if s in comments and comments[s] != GENERATED)
            if foreign:
                raise PolicyError(f"schemas not generated by sync_policies: {', '.join(foreign)}")
            for schema in sorted(s for s, comment in comments.items() if comment == GENERATED):
                conn.execute(f"DROP SCHEMA {quote(schema)} CASCADE")
            for statement in generated:
                conn.execute(statement)
            postgres.replace_policy_effective(conn, policy.effective(tables))
    log.info("policies synced for %s tables", len(tables))


def output_checks(policy: Policy, role: str, dataset_id: str, columns: list[str]) -> list[tuple[str, str, str]]:
    checks = []
    for column in columns:
        action = policy.action(role, dataset_id, column)
        name = quote(column)
        if action == DENY:
            flag = quote(column + DENIED_SUFFIX)
            checks.append((column, action, f"count({name}) + count(*) FILTER (WHERE {flag} IS NOT TRUE)"))
        elif action == ALLOW:
            checks.append((column, action, f"count({name})"))
        else:
            pattern = literal(MASKS[action.removeprefix(MASK)][1])
            checks.append((column, action, f"count({name}) FILTER (WHERE {name}::text ~ {pattern})"))
    return checks


def output_errors(conn, policy: Policy, role: str, dataset_id: str, columns: list[str]) -> list[str]:
    schema, table = dataset_id.split(".", 1)
    checks = output_checks(policy, role, dataset_id, columns)
    base = ", ".join(f"count({quote(column)})" for column in columns)
    seen = ", ".join(expression for _, _, expression in checks)
    conn.execute("BEGIN ISOLATION LEVEL REPEATABLE READ")
    try:
        expected = conn.execute(f"SELECT {base} FROM {qualified(schema, table)}").fetchone()
        conn.execute(f"SET LOCAL ROLE {quote(policy.roles[role])}")
        actual = conn.execute(f"SELECT {seen} FROM {qualified(*view_name(dataset_id))}").fetchone()
    finally:
        conn.execute("ROLLBACK")
    return [
        f"{role} {dataset_id}.{column}: view output does not match {action}"
        for (column, action, _), want, got in zip(checks, expected, actual, strict=True)
        if got != (0 if action == DENY else want)
    ]


def verify_policies() -> None:
    if mode() == "offline":
        stub("verify_policies")
        return
    policy = load_policy()
    with postgres.connect() as conn:
        tables = postgres.serving_tables(conn)
        policy.check(tables)
        expected = set(policy.effective(tables))
        stored = set(postgres.policy_effective(conn))
        errors = [f"ops.policy_effective differs for {' '.join(row)}" for row in sorted(expected ^ stored)]
        for role, login in policy.roles.items():
            for dataset_id, columns in tables.items():
                schema, table = dataset_id.split(".", 1)
                reader = role in policy.readers.get(dataset_id, [])
                base, view = postgres.select_privileges(
                    conn, login, qualified(schema, table), qualified(*view_name(dataset_id)), columns
                )
                if base:
                    errors.append(f"{role} can read {dataset_id} directly")
                errors += [
                    f"{role} {dataset_id}.{column}: view privilege is {has}, expected {reader}"
                    for column, has in zip(columns, view, strict=True)
                    if has != reader
                ]
                if reader and all(view):
                    errors += output_errors(conn, policy, role, dataset_id, columns)
    if errors:
        raise PolicyError("; ".join(errors))
    log.info("policies verified for %s roles and %s tables", len(policy.roles), len(tables))


def effective_matrix() -> list[dict[str, Any]]:
    if mode() == "offline":
        return stub("effective_matrix", [])
    with postgres.connect() as conn:
        rows = postgres.policy_effective(conn, view=True)
    return [dict(zip(("role", "dataset_id", "column", "action"), row, strict=True)) for row in rows]


def can_export(dataset_id: str, role: str) -> tuple[bool, str]:
    return stub("can_export", (False, "not implemented"), dataset_id=dataset_id, role=role)


def can_edit(dataset_id: str, role: str) -> tuple[bool, str]:
    policy = load_policy()
    editors = policy.editors.get(dataset_id, [])
    if role in editors:
        return True, ""
    allowed = ", ".join(editors) or "no role"
    return False, f"{role or 'a request with no role'} may not edit {dataset_id}; only {allowed} can"
