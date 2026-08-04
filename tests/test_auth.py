"""Contract: authentication, role scoping, sharing, public links, comments."""

import pytest
from fastapi.testclient import TestClient

from conftest import build_client, login_as

RAG_PRD = "- grounded llm answers over the knowledge base on databricks"


def _admin(tmp_path, monkeypatch) -> TestClient:
    return build_client(tmp_path, monkeypatch, role="admin")


def _create_estimate(client, name="Est", opportunity_id=None):
    body = {"project_name": name, "prd_text": RAG_PRD, "client_context": {"tech_stack": ["Databricks"]}}
    if opportunity_id:
        body["opportunity_id"] = opportunity_id
    r = client.post("/api/estimates", json=body)
    assert r.status_code == 200, r.text
    return r.json()["estimate_id"]


def test_login_and_me(tmp_path, monkeypatch):
    c = _admin(tmp_path, monkeypatch)
    me = c.get("/api/auth/me").json()
    assert me["role"] == "admin"
    bad = c.post("/api/auth/login", json={"email": "admin@teamsparq.com", "password": "wrong"})
    assert bad.status_code == 401


def test_unauthenticated_is_rejected(tmp_path, monkeypatch):
    c = build_client(tmp_path, monkeypatch, role="admin")
    c.headers.pop("Authorization")
    assert c.get("/api/estimates").status_code == 401


def test_user_sees_only_own_admin_sees_all(tmp_path, monkeypatch):
    c = _admin(tmp_path, monkeypatch)
    admin_est = _create_estimate(c, "Admin est")
    login_as(c, "user")
    user_est = _create_estimate(c, "User est")

    user_list = {e["estimate_id"] for e in c.get("/api/estimates").json()}
    assert user_est in user_list and admin_est not in user_list

    login_as(c, "admin")
    admin_list = {e["estimate_id"] for e in c.get("/api/estimates").json()}
    assert {admin_est, user_est} <= admin_list


def test_share_by_email_and_name(tmp_path, monkeypatch):
    c = _admin(tmp_path, monkeypatch)
    est = _create_estimate(c, "Shared est")

    # Share by email (view) — user can now see it.
    assert c.post(f"/api/estimates/{est}/shares", json={"principal": "user@teamsparq.com", "permission": "view"}).status_code == 200
    login_as(c, "user")
    assert c.get(f"/api/estimates/{est}").status_code == 200
    assert c.post(f"/api/estimates/{est}/recompute", json={"ai_boost": 0.2}).status_code == 403  # view only

    # Share by NAME with comment permission.
    login_as(c, "admin")
    assert c.post(f"/api/estimates/{est}/shares", json={"principal": "Sample User", "permission": "comment"}).status_code == 200
    login_as(c, "user")
    assert c.post(f"/api/estimates/{est}/comments", json={"body": "looks good"}).status_code == 200
    assert len(c.get(f"/api/estimates/{est}/comments").json()) == 1


def test_public_share_link_no_login(tmp_path, monkeypatch):
    c = _admin(tmp_path, monkeypatch)
    est = _create_estimate(c, "Public est")
    token = c.post(f"/api/estimates/{est}/share-link").json()["token"]

    # Anonymous client (no auth header) can view via the token.
    c.headers.pop("Authorization")
    r = c.get(f"/api/shared/{token}")
    assert r.status_code == 200 and r.json()["estimate_id"] == est
    assert c.get(f"/api/shared/deadbeef").status_code == 404


def test_client_read_only_on_assigned_opportunity(tmp_path, monkeypatch):
    c = _admin(tmp_path, monkeypatch)
    account = c.post("/api/accounts", json={"name": "Acme"}).json()
    opp = c.post("/api/opportunities", json={"name": "RAG", "account_id": account["id"],
                                             "notion_page_ref": "https://notion.so/demo"}).json()
    est = _create_estimate(c, "Opp est", opportunity_id=opp["id"])

    client_user = next(u for u in c.get("/api/users").json() if u["email"] == "client@teamsparq.com")
    c.post(f"/api/users/{client_user['id']}/assign", json={"account_id": account["id"]})

    # Opportunity carries account, estimates, and (stub) Notion notes.
    opp_detail = c.get(f"/api/opportunities/{opp['id']}").json()
    assert opp_detail["account"]["name"] == "Acme"
    assert opp_detail["notion_notes"]

    login_as(c, "client")
    assert c.get(f"/api/estimates/{est}").status_code == 200          # assigned -> view
    assert c.post(f"/api/estimates/{est}/recompute", json={}).status_code == 403  # read only
    assert c.post("/api/estimates", json={"project_name": "x", "prd_text": RAG_PRD}).status_code == 403  # cannot create


def test_admin_only_endpoints(tmp_path, monkeypatch):
    c = _admin(tmp_path, monkeypatch)
    login_as(c, "user")
    assert c.get("/api/users").status_code == 403
    assert c.post("/api/accounts", json={"name": "Nope"}).status_code == 403
