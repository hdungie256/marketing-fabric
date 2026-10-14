import logging
import os
from pathlib import Path
from typing import Any

log = logging.getLogger("fabric_control")

ROOT = Path(__file__).resolve().parent.parent


def mode() -> str:
    return os.environ.get("FABRIC_CONTROL_MODE", "offline")


def contracts_dir() -> Path:
    return Path(os.environ.get("FABRIC_CONTRACTS_DIR", ROOT / "contracts"))


def jobs_dir() -> Path:
    return Path(os.environ.get("FABRIC_JOBS_DIR", ROOT / "pipelines" / "jobs"))


def stub(name: str, default: Any = None, **kwargs: Any) -> Any:
    if mode() != "offline":
        raise NotImplementedError(name)
    log.info("offline %s %s", name, kwargs)
    return default
