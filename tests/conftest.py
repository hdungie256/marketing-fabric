import pytest


@pytest.fixture(autouse=True)
def offline_mode(monkeypatch):
    monkeypatch.setenv("FABRIC_CONTROL_MODE", "offline")
