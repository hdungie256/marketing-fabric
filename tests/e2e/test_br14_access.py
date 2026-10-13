import fabric_control as fc
from fabric_control.clients import postgres
from fabric_control.policy import load_policy

# FR-20 per tag: role -> action; roles not listed get the fallback.
EXPECTED = {
    "Finance.sku_cost": ({"UG04": "allow"}, "deny"),
    "Finance.aggregate": ({"UG03": "allow", "UG04": "allow"}, "deny"),
    "Sensitivity.direct_identifier": ({"UG02": "allow"}, "mask:partial"),
}


def test_access_matrix_matches_fr20_and_verified_policy():
    fc.run_migrations()
    fc.sync_policies()
    fc.verify_policies()
    policy = load_policy()
    matrix = {(r["role"], r["dataset_id"], r["column"]): r["action"] for r in fc.effective_matrix()}
    with postgres.connect() as conn:
        assert set(matrix.items()) == {((r, d, c), a) for r, d, c, a in policy.effective(postgres.serving_tables(conn))}
    checked = 0
    for (role, dataset_id, column), action in matrix.items():
        tag = policy.column_tags[dataset_id][column]
        if tag not in EXPECTED or role not in policy.readers.get(dataset_id, []):
            continue
        overrides, fallback = EXPECTED[tag]
        assert action == overrides.get(role, fallback), (role, dataset_id, column)
        checked += 1
    assert checked, "no FR-20 tagged column is served yet"
