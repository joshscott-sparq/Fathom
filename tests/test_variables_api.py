"""Contract: /api/variables and /api/tshirt-scale (D31, D34) — open reads,
admin-only writes, merge-not-replace override semantics."""

import pytest

from conftest import build_client


@pytest.fixture()
def admin_client(tmp_path, monkeypatch):
    return build_client(tmp_path, monkeypatch, role="admin")


@pytest.fixture()
def user_client(tmp_path, monkeypatch):
    return build_client(tmp_path, monkeypatch, role="user")


def test_get_variables_open_to_any_authenticated_user(user_client):
    resp = user_client.get("/api/variables")
    assert resp.status_code == 200
    body = resp.json()
    assert body["effective"]["avg_story_pts"] == 9.0
    assert body["overridden_fields"] == []


def test_put_variables_requires_admin(user_client):
    resp = user_client.put("/api/variables", json={"avg_story_pts": 12})
    assert resp.status_code == 403


def test_put_variables_merges_not_replaces(admin_client):
    r1 = admin_client.put("/api/variables", json={"avg_story_pts": 12})
    assert r1.status_code == 200
    assert r1.json()["overridden_fields"] == ["avg_story_pts"]

    r2 = admin_client.put("/api/variables", json={"days_per_story_point": 1.5})
    assert r2.status_code == 200
    assert set(r2.json()["overridden_fields"]) == {"avg_story_pts", "days_per_story_point"}
    assert r2.json()["effective"]["avg_story_pts"] == 12.0
    assert r2.json()["effective"]["days_per_story_point"] == 1.5


def test_get_tshirt_scale_open_to_any_authenticated_user(user_client):
    resp = user_client.get("/api/tshirt-scale")
    assert resp.status_code == 200
    assert resp.json()["sizes"]["M"] == {"epic": 50, "feature": 12.5, "story": 5}
    assert resp.json()["overridden_sizes"] == []


def test_put_tshirt_scale_requires_admin(user_client):
    resp = user_client.put("/api/tshirt-scale", json={"M": {"epic": 55}})
    assert resp.status_code == 403


def test_put_tshirt_scale_merges_within_a_size(admin_client):
    resp = admin_client.put("/api/tshirt-scale", json={"M": {"epic": 55}})
    assert resp.status_code == 200
    assert resp.json()["sizes"]["M"]["epic"] == 55
    assert resp.json()["sizes"]["M"]["story"] == 5  # untouched sibling preserved
    assert resp.json()["overridden_sizes"] == ["M"]


def test_new_estimate_reflects_admin_variable_override(admin_client):
    admin_client.put("/api/variables", json={"avg_story_pts": 30})
    created = admin_client.post("/api/estimates", json={
        "project_name": "RAG", "prd_text": "- grounded llm answers on databricks",
        "client_context": {"tech_stack": ["Databricks"]},
    }).json()
    assert created["graph"]["variables"]["avg_story_pts"] == 30.0
