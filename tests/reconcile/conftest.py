import os

import pytest

collect_ignore_glob = [] if os.environ.get("FABRIC_E2E") == "1" else ["test_*.py"]


@pytest.fixture(autouse=True)
def online_mode(monkeypatch):
    monkeypatch.setenv("FABRIC_CONTROL_MODE", "online")
