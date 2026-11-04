"""Services that start Airflow DAGs get every variable the Airflow client reads (BR15 Reload from the UI)."""

import re
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.parametrize("service", ["streamlit", "api"])
def test_service_has_the_airflow_client_env(service):
    client = (ROOT / "fabric_control/clients/airflow.py").read_text()
    needed = set(re.findall(r'os\.environ\["(\w+)"\]', client))
    compose = yaml.safe_load((ROOT / "compose/docker-compose.yml").read_text())
    env = set(compose["services"][service]["environment"])
    assert needed and needed <= env, sorted(needed - env)
