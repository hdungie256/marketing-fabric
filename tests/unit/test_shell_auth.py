import pytest

from app.shell import auth
from app.shell.roles import ROLES

PASSWORDS = {
    "MARKETING_ANALYST_DB_PASSWORD": "pw1",
    "CRM_MARKETING_DB_PASSWORD": "pw2",
    "MARKETING_MANAGER_DB_PASSWORD": "pw3",
    "FINANCE_CONTROLLER_DB_PASSWORD": "pw4",
    "DATA_STEWARD_DB_PASSWORD": "pw5",
    "DATA_OPS_DB_PASSWORD": "pw6",
}


@pytest.fixture
def env(monkeypatch):
    for name, value in PASSWORDS.items():
        monkeypatch.setenv(name, value)
    return monkeypatch


def test_roles_follow_prd_names_in_order():
    assert list(ROLES) == ["UG01", "UG02", "UG03", "UG04", "UG05", "UG06"]
    assert ROLES["UG03"].label == "Marketing Manager (UG03)"
    assert ROLES["UG05"].label == "Marketing Data Steward (UG05)"
    assert ROLES["UG01"].password_env == "MARKETING_ANALYST_DB_PASSWORD"


def test_db_user_defaults_and_can_be_overridden(env):
    assert ROLES["UG04"].db_user == "finance_controller"
    env.setenv("FINANCE_CONTROLLER_DB_USER", "ug04_login")
    assert ROLES["UG04"].db_user == "ug04_login"


def test_verify_accepts_the_role_password(env):
    assert auth.verify("UG01", "pw1")


def test_verify_normalizes_code(env):
    assert auth.verify(" ug01 ", "pw1")
    assert auth.normalize(" ug01 ") == "UG01"


@pytest.mark.parametrize("code,password", [("UG01", "pw2"), ("UG09", "pw1"), ("", ""), ("UG01", "")])
def test_verify_rejects_wrong_credentials(env, code, password):
    assert not auth.verify(code, password)


def test_empty_password_env_counts_as_missing_and_never_logs_in(env):
    env.setenv("MARKETING_ANALYST_DB_PASSWORD", "")
    assert auth.missing_env() == ["MARKETING_ANALYST_DB_PASSWORD"]
    assert not auth.verify("UG01", "")


def test_missing_env_lists_unset_variables(env):
    env.delenv("DATA_OPS_DB_PASSWORD")
    assert auth.missing_env() == ["DATA_OPS_DB_PASSWORD"]


def test_empty_db_user_env_falls_back_to_default(env):
    env.setenv("FINANCE_CONTROLLER_DB_USER", "")
    assert ROLES["UG04"].db_user == "finance_controller"
