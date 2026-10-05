import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Role:
    code: str
    name: str
    env_prefix: str

    @property
    def password_env(self) -> str:
        return f"{self.env_prefix}_DB_PASSWORD"

    @property
    def db_user(self) -> str:
        return os.environ.get(f"{self.env_prefix}_DB_USER", self.env_prefix.lower())

    @property
    def label(self) -> str:
        return f"{self.name} ({self.code})"


ROLES: dict[str, Role] = {
    role.code: role
    for role in (
        Role("UG01", "Marketing Analyst", "MARKETING_ANALYST"),
        Role("UG02", "CRM / Customer Marketing", "CRM_MARKETING"),
        Role("UG03", "Marketing Manager", "MARKETING_MANAGER"),
        Role("UG04", "Finance / Business Controller", "FINANCE_CONTROLLER"),
        Role("UG05", "Marketing Data Steward", "DATA_STEWARD"),
        Role("UG06", "Marketing Data Ops", "DATA_OPS"),
    )
}
