"""Contract: auto-save (rebuild in place) and clone."""

from conftest import build_client

RAG_PRD = "- grounded llm answers over the knowledge base on databricks"
RAG_PRD_MORE = RAG_PRD + "\n- add an evaluation harness and observability"


def test_rebuild_saves_in_place_without_new_version(tmp_path, monkeypatch):
    c = build_client(tmp_path, monkeypatch, role="admin")
    created = c.post("/api/estimates", json={"project_name": "Live", "prd_text": RAG_PRD, "client_context": {"tech_stack": ["Databricks"]}}).json()
    est = created["estimate_id"]
    assert created["version"] == 1

    # Auto-save with more info: same version (in place), more work items.
    r = c.post(f"/api/estimates/{est}/rebuild", json={"project_name": "Live", "prd_text": RAG_PRD_MORE, "client_context": {"tech_stack": ["Databricks"]}})
    assert r.status_code == 200, r.text
    assert r.json()["version"] == 1  # no version bump on auto-save
    # Content updated (reflects the new PRD).
    assert r.json()["graph"]["requirements"]


def test_clone_creates_new_estimate_not_active(tmp_path, monkeypatch):
    c = build_client(tmp_path, monkeypatch, role="admin")
    account = c.post("/api/accounts", json={"name": "Acme"}).json()
    opp = c.post("/api/opportunities", json={"name": "RAG", "account_id": account["id"]}).json()
    created = c.post("/api/estimates", json={"project_name": "Original", "prd_text": RAG_PRD,
                                             "client_context": {"tech_stack": ["Databricks"]}, "opportunity_id": opp["id"]}).json()
    original = created["estimate_id"]

    clone = c.post(f"/api/estimates/{original}/clone").json()
    assert clone["estimate_id"] != original
    assert clone["version"] == 1
    assert clone["graph"]["project_name"].endswith("(clone)")

    # Original is the opportunity's active estimate; the clone is not.
    detail = c.get(f"/api/opportunities/{opp['id']}").json()
    assert detail["opportunity"]["active_estimate_id"] == original
    est_ids = {e["estimate_id"] for e in detail["estimates"]}
    assert {original, clone["estimate_id"]} <= est_ids  # both belong to the opportunity


def test_client_cannot_clone(tmp_path, monkeypatch):
    from conftest import login_as

    c = build_client(tmp_path, monkeypatch, role="admin")
    account = c.post("/api/accounts", json={"name": "Acme"}).json()
    opp = c.post("/api/opportunities", json={"name": "RAG", "account_id": account["id"]}).json()
    est = c.post("/api/estimates", json={"project_name": "Original", "prd_text": RAG_PRD,
                                         "client_context": {"tech_stack": ["Databricks"]}, "opportunity_id": opp["id"]}).json()["estimate_id"]
    client_user = next(u for u in c.get("/api/users").json() if u["email"] == "client@teamsparq.com")
    c.post(f"/api/users/{client_user['id']}/assign", json={"account_id": account["id"]})

    login_as(c, "client")
    assert c.post(f"/api/estimates/{est}/clone").status_code == 403
