import os
from pathlib import Path
from typing import Protocol

import pandas as pd
import psycopg
from psycopg import sql

from app.shell import session
from app.shell.errors import NotPermittedError
from app.shell.roles import ROLES, Role
from fabric_control import load_registry
from fabric_control.config import contracts_dir

FIXTURES_DIR = contracts_dir() / "fixtures"
MODES = ("fixture", "pg")


class DataSource(Protocol):
    def read(self, dataset_id: str) -> pd.DataFrame: ...


def data_mode() -> str:
    mode = os.environ.get("APP_DATA_MODE", "fixture")
    if mode not in MODES:
        raise ValueError(f"APP_DATA_MODE must be 'fixture' or 'pg', got {mode!r}")
    return mode


def view_for(dataset_id: str, registry: dict | None = None) -> str:
    registry = load_registry() if registry is None else registry
    entry = registry.get(dataset_id)
    if entry is None:
        raise ValueError(f"{dataset_id}: not in contracts registry")
    parts = entry["om_fqn"].split(".")
    if len(parts) != 4 or parts[:2] != ["serving", "serving"]:
        raise ValueError(f"{dataset_id}: not a Postgres serving dataset ({entry['om_fqn']})")
    return f"{parts[2]}_v.{parts[3]}"


class FixtureSource:
    def __init__(self, directory: Path = FIXTURES_DIR):
        self.directory = directory

    def read(self, dataset_id: str) -> pd.DataFrame:
        path = self.directory / f"{dataset_id}.parquet"
        if not path.exists():
            raise FileNotFoundError(f"No fixture for {dataset_id}: expected {path}")
        return pd.read_parquet(path)


class PgSource:
    def __init__(self, role: Role, registry: dict | None = None):
        self.role = role
        self._registry = registry

    def _connect(self) -> psycopg.Connection:
        return psycopg.connect(
            host=os.environ.get("DB_HOST", "postgresql"),
            port=int(os.environ.get("DB_PORT", "5432")),
            dbname="serving",
            user=self.role.db_user,
            password=os.environ[self.role.password_env],
            autocommit=True,
            options="-c default_transaction_read_only=on",
        )

    def read(self, dataset_id: str) -> pd.DataFrame:
        schema, table = view_for(dataset_id, self._registry).split(".")
        query = sql.SQL("SELECT * FROM {}.{}").format(sql.Identifier(schema), sql.Identifier(table))
        try:
            with self._connect() as conn:
                cursor = conn.execute(query)
                return pd.DataFrame(cursor.fetchall(), columns=[d.name for d in cursor.description])
        except psycopg.errors.InsufficientPrivilege as e:
            raise NotPermittedError(dataset_id) from e


def current_source() -> DataSource:
    if data_mode() == "fixture":
        return FixtureSource()
    return PgSource(ROLES[session.role()])
