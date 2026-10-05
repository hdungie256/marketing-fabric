import hmac
import os

from app.shell.roles import ROLES


def normalize(code: str) -> str:
    return code.strip().upper()


def missing_env() -> list[str]:
    return [role.password_env for role in ROLES.values() if not os.environ.get(role.password_env)]


def verify(code: str, password: str) -> bool:
    role = ROLES.get(normalize(code))
    if role is None:
        return False
    expected = os.environ.get(role.password_env, "")
    return bool(expected) and hmac.compare_digest(password.encode(), expected.encode())
