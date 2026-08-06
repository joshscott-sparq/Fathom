"""Shared test helpers: build a TestClient authenticated as a seeded role."""

import importlib

import pytest
from fastapi.testclient import TestClient

SAMPLE_CREDS = {
    "admin": ("admin@teamsparq.com", "admin123"),
    "user": ("user@teamsparq.com", "user123"),
    "client": ("client@teamsparq.com", "client123"),
}


@pytest.fixture(autouse=True)
def _disable_llm_by_default(monkeypatch):
    """No test should call the real Anthropic API — it burns tokens and time.

    Tests that need to exercise the LLM code path inject a FakeLLM client
    (see test_llm.py) rather than relying on a real key; this fixture makes
    that the enforced default regardless of whether ANTHROPIC_API_KEY happens
    to be set in the developer's environment (e.g. via .env).
    """
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)


def build_client(tmp_path, monkeypatch, role: str = "admin") -> TestClient:
    monkeypatch.setenv("FATHOM_DB", str(tmp_path / "api.db"))
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    from fathom.api import app as app_module

    importlib.reload(app_module)
    client = TestClient(app_module.app)
    if role:
        login_as(client, role)
    return client


def login_as(client: TestClient, role: str) -> None:
    email, password = SAMPLE_CREDS[role]
    resp = client.post("/api/auth/login", json={"email": email, "password": password})
    assert resp.status_code == 200, resp.text
    client.headers.update({"Authorization": f"Bearer {resp.json()['token']}"})
