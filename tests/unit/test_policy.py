import pytest
import yaml

import fabric_control as fc
from app.shell.roles import ROLES
from fabric_control.contracts import columns, load_schema
from fabric_control.policy import GENERATED, PolicyError, load_policy, statements, view_sql

ROLE_LOGINS = {"UG01": "analyst", "UG02": "crm", "UG04": "finance"}
TAGS = [
    {"name": "internal", "classification": "Sensitivity", "description": "d", "actions": {"default": "allow"}},
    {
        "name": "identifier",
        "classification": "Sensitivity",
        "description": "d",
        "actions": {"default": "mask:partial", "UG02": "allow"},
    },
    {"name": "cost", "classification": "Finance", "description": "d", "actions": {"default": "deny", "UG04": "allow"}},
    {"name": "undecided", "classification": "Finance", "description": "d"},
]
COLUMNS = {
    "mart_x.orders": {
        "order_id": "Sensitivity.internal",
        "customer_id": "Sensitivity.identifier",
        "unit_cost": "Finance.cost",
        "margin": "Finance.undecided",
    }
}
TABLES = {"mart_x.orders": ["order_id", "customer_id", "unit_cost", "margin"]}


def write(tmp_path, tags=TAGS, tagged=COLUMNS, read=None, extra=None):
    (tmp_path / "tags").mkdir(exist_ok=True)
    (tmp_path / "tags" / "a.yml").write_text(yaml.safe_dump({"tags": tags, "columns": tagged}))
    for name, doc in (extra or {}).items():
        (tmp_path / "tags" / name).write_text(yaml.safe_dump(doc))
    matrix = {"roles": ROLE_LOGINS, "read": {"mart_x.orders": ["UG01", "UG02"]} if read is None else read}
    (tmp_path / "access_matrix.yml").write_text(yaml.safe_dump(matrix))
    return tmp_path


def test_repo_roles_match_app_logins():
    assert load_policy().roles == {code: role.db_user for code, role in ROLES.items()}


def test_repo_serving_contract_columns_are_tagged():
    policy = load_policy()
    serving = [d for d, entry in fc.load_registry().items() if entry["om_fqn"].startswith("serving.")]
    assert serving
    for dataset_id in serving:
        names = {name for name, _ in columns(load_schema(dataset_id))}
        assert names <= set(policy.column_tags.get(dataset_id, {})), dataset_id


def test_untagged_column_fails_closed(tmp_path):
    policy = load_policy(write(tmp_path))
    with pytest.raises(PolicyError, match=r"untagged serving columns: mart_x.orders.discount, mart_x.new.id"):
        statements(policy, {"mart_x.orders": [*TABLES["mart_x.orders"], "discount"], "mart_x.new": ["id"]})


def test_unknown_tag_role_action_and_dataset_fail(tmp_path):
    with pytest.raises(PolicyError, match="unknown tag 'Sensitivity.missing'"):
        load_policy(write(tmp_path, tagged={"mart_x.orders": {"order_id": "Sensitivity.missing"}}))
    with pytest.raises(PolicyError, match="invalid action 'mask:reverse'"):
        load_policy(write(tmp_path, tags=[{**TAGS[0], "actions": {"default": "mask:reverse"}}], tagged={}))
    with pytest.raises(PolicyError, match="unknown role UG09"):
        load_policy(write(tmp_path, tags=[{**TAGS[0], "actions": {"UG09": "allow"}}], tagged={}))
    with pytest.raises(PolicyError, match="unknown roles"):
        load_policy(write(tmp_path, read={"mart_x.orders": ["UG09"]}))
    with pytest.raises(PolicyError, match="unknown datasets: mart_x.gone"):
        load_policy(write(tmp_path, read={"mart_x.gone": ["UG01"]})).check(TABLES)


def test_dataset_tagged_in_two_files_names_both(tmp_path):
    with pytest.raises(PolicyError, match=r"a.yml and b.yml"):
        load_policy(write(tmp_path, extra={"b.yml": {"tags": [], "columns": COLUMNS}}))


def test_effective_action_per_role(tmp_path):
    policy = load_policy(write(tmp_path))
    effective = {(role, column): action for role, _, column, action in policy.effective(TABLES)}
    assert effective["UG01", "order_id"] == "allow"
    assert effective["UG01", "customer_id"] == "mask:partial"
    assert effective["UG02", "customer_id"] == "allow"
    assert effective["UG01", "unit_cost"] == "deny"
    assert effective["UG02", "margin"] == "deny"
    assert {action for (role, _), action in effective.items() if role == "UG04"} == {"deny"}
    assert len(effective) == len(ROLE_LOGINS) * 4


def test_view_keeps_column_names_and_applies_actions(tmp_path):
    sql = view_sql(load_policy(write(tmp_path)), "mart_x.orders", TABLES["mart_x.orders"])
    assert sql.startswith('CREATE VIEW "mart_x_v"."orders" AS SELECT "order_id", CASE')
    assert sql.endswith('FROM "mart_x"."orders"')
    assert "WHEN current_user IN ('crm') THEN \"customer_id\"::text" in sql
    assert (
        "WHEN current_user IN ('analyst', 'finance') THEN \"mart_x_v\".policy_mask_partial(\"customer_id\"::text)"
        in sql
    )
    assert "customer_id__denied" not in sql
    assert 'CASE WHEN current_user IN (\'finance\') THEN "unit_cost" END AS "unit_cost"' in sql
    assert "current_user NOT IN ('finance') AS \"unit_cost__denied\"" in sql
    assert 'CASE WHEN false THEN "margin" END AS "margin", true AS "margin__denied"' in sql


def test_statements_grant_views_only(tmp_path):
    generated = statements(load_policy(write(tmp_path)), TABLES)
    grants = [s for s in generated if s.startswith("GRANT")]
    assert grants == [
        'GRANT SELECT ON "mart_x_v"."orders" TO "analyst", "crm"',
        'GRANT USAGE ON SCHEMA "mart_x_v" TO "analyst", "crm"',
    ]
    assert 'REVOKE ALL ON ALL TABLES IN SCHEMA "mart_x" FROM "analyst", "crm", "finance"' in generated
    assert f'COMMENT ON VIEW "mart_x_v"."orders" IS \'{GENERATED}\'' in generated
    assert f"COMMENT ON SCHEMA \"mart_x_v\" IS '{GENERATED}'" in generated
    assert f"COMMENT ON FUNCTION \"mart_x_v\".policy_mask_partial(text) IS '{GENERATED}'" in generated
    created = [s.split(" AS ")[0] for s in generated if s.startswith("CREATE VIEW")]
    assert created == ['CREATE VIEW "mart_x_v"."orders"']


def test_writers_get_their_schema_only(tmp_path):
    tagged = {"app.segments": {"id": "Sensitivity.internal"}, "ops.runs": {"id": "Sensitivity.internal"}}
    policy = load_policy(write(tmp_path, tagged=tagged, read={}))
    generated = statements(policy, {"app.segments": ["id"], "ops.runs": ["id"]})
    assert 'GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA "app" TO "app_writer"' in generated
    assert 'GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA "ops" TO "ops_writer"' in generated
    assert not [s for s in generated if s.startswith("GRANT") and "_v" in s]


def test_offline_calls_do_nothing(monkeypatch):
    monkeypatch.setenv("FABRIC_CONTROL_MODE", "offline")
    assert fc.sync_policies() is None
    assert fc.verify_policies() is None
    assert fc.effective_matrix() == []
