import os
import time
from pathlib import Path

import pytest

pytest.importorskip("streamlit")
from streamlit.testing.v1 import AppTest  # noqa: E402

MAIN = str(Path(__file__).resolve().parents[2] / "app" / "main.py")


def test_campaign_overview_renders_from_pg_under_3s(monkeypatch):
    monkeypatch.setenv("APP_DATA_MODE", "pg")
    at = AppTest.from_file(MAIN, default_timeout=30).run()
    at.text_input(key="_login_code").input("UG01")
    at.text_input(key="_login_password").input(os.environ["MARKETING_ANALYST_DB_PASSWORD"])
    started = time.perf_counter()
    at.button[0].click().run()
    elapsed = time.perf_counter() - started
    assert not at.exception
    text = " ".join(m.value for m in at.markdown)
    assert "Could not load this page" not in text
    assert "1,290" in [m.value for m in at.markdown]
    assert elapsed < 3, f"Campaign Overview took {elapsed:.2f}s"
