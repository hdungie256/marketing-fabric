import os
from pathlib import Path

from fabric_control.config import ROOT, mode, stub

PLATFORM = "_platform"


def migration_dirs(root: Path | None = None) -> list[Path]:
    root = root or Path(os.environ.get("FABRIC_MIGRATIONS_DIR", ROOT / "migrations"))
    dirs = sorted(p for p in root.iterdir() if p.is_dir() and any(p.glob("*.sql")))
    return sorted(dirs, key=lambda p: p.name != PLATFORM)


def yoyo_url(dsn: str) -> str:
    return dsn.replace("postgresql://", "postgresql+psycopg://", 1)


def run_migrations() -> None:
    if mode() == "offline":
        stub("run_migrations")
        return
    from yoyo import get_backend, read_migrations

    backend = get_backend(yoyo_url(os.environ["SERVING_DB_DSN"]))
    migrations = read_migrations(*(str(d) for d in migration_dirs()))
    with backend.lock():
        backend.apply_migrations(backend.to_apply(migrations))
