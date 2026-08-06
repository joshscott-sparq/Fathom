"""Contract: rate-card parsing, repricing, and the rates API."""

import io

import pytest
from fastapi.testclient import TestClient

from fathom.core.rates import RateCard, parse_rate_file, recost
from fathom.models.enums import Location
from fathom.service import EstimateService
from fathom.persistence.store import SQLiteEstimateRepository
from fathom.models.results import ClientContext

RAG_PRD = "- retrieval augmented generation over the knowledge base on databricks\n- grounded llm answers"

ONSHORE = b"discipline,tier,location,day_rate\nAI & ML,Senior,US,2000\nData Engineering,Senior,US,1800\n"
BLENDED = b"discipline,tier,location,day_rate\nAI & ML,Senior,US,1000\nData Engineering,Senior,US,900\n"


def test_parse_csv_rates():
    rows = parse_rate_file(ONSHORE, "rates.csv")
    assert len(rows) == 2
    card = RateCard(rows)
    assert card.rate_for("AI & ML", "Senior", Location.US) == 2000
    # US fallback when the exact location is absent.
    assert card.rate_for("AI & ML", "Senior", Location.NS) == 2000


def test_parse_rejects_missing_columns():
    with pytest.raises(ValueError):
        parse_rate_file(b"foo,bar\n1,2\n", "bad.csv")


def test_parse_yaml_rates():
    y = b"rates:\n  - {discipline: Web, tier: Senior, location: US, day_rate: 1500}\n"
    rows = parse_rate_file(y, "rates.yaml")
    assert rows[0].discipline == "Web" and rows[0].day_rate == 1500


def test_recost_changes_price_not_effort(tmp_path):
    svc = EstimateService(repo=SQLiteEstimateRepository(tmp_path / "r.db"))
    svc.create_rate_card("onshore", parse_rate_file(ONSHORE, "onshore.csv"))
    stored, _ = svc.create_estimate("RAG", RAG_PRD, ClientContext(tech_stack=["Databricks"]))
    onshore_cost = stored.graph.deterministic.total_cost
    effort = stored.graph.monte_carlo.effort_points.p50
    duration = stored.graph.monte_carlo.duration_sprints.p50

    # Switch to the cheaper blended leverage card and re-cost.
    svc.create_rate_card("blended", parse_rate_file(BLENDED, "blended.csv"))
    repriced = svc.recost_estimate(stored.estimate_id)
    assert repriced.version == 2
    # Cheaper card -> lower cost; effort and duration unchanged.
    assert repriced.graph.deterministic.total_cost < onshore_cost
    assert repriced.graph.monte_carlo.effort_points.p50 == effort
    assert repriced.graph.monte_carlo.duration_sprints.p50 == duration


@pytest.fixture()
def client(tmp_path, monkeypatch):
    from conftest import build_client

    return build_client(tmp_path, monkeypatch, role="admin")


def test_rate_card_management(client):
    # A seeded default card exists and is active.
    cards = client.get("/api/rate-cards").json()
    assert len(cards) == 1
    default = cards[0]
    assert default["is_default"] and default["is_active"]

    # Upload a new card -> saved and becomes active; default no longer active.
    up = client.post("/api/rate-cards", files={"file": ("onshore.csv", ONSHORE, "text/csv")}, data={"name": "Onshore"})
    assert up.status_code == 200, up.text
    new_id = up.json()["id"]
    cards = client.get("/api/rate-cards").json()
    assert len(cards) == 2
    active = [c for c in cards if c["is_active"]]
    assert len(active) == 1 and active[0]["id"] == new_id

    # Re-activate the default.
    client.post(f"/api/rate-cards/{default['id']}/activate")
    assert client.get("/api/rates").json()["source"] == default["name"]

    # Default cannot be deleted; the custom card can.
    assert client.delete(f"/api/rate-cards/{default['id']}").status_code == 400
    assert client.delete(f"/api/rate-cards/{new_id}").status_code == 200
    assert len(client.get("/api/rate-cards").json()) == 1


def test_update_rate_card_rows(client):
    up = client.post("/api/rate-cards", files={"file": ("onshore.csv", ONSHORE, "text/csv")}, data={"name": "Onshore"})
    card_id = up.json()["id"]

    resp = client.put(f"/api/rate-cards/{card_id}", json={"rows": [
        {"discipline": "AI & ML", "tier": "Senior", "location": "US", "day_rate": 2400},
    ]})
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert len(body["rates"]) == 1
    assert body["rates"][0]["day_rate"] == 2400

    # Persisted, not just returned.
    cards = client.get("/api/rate-cards").json()
    updated = next(c for c in cards if c["id"] == card_id)
    assert updated["summary"]["rows"] == 1


def test_update_rate_card_404(client):
    resp = client.put("/api/rate-cards/does-not-exist", json={"rows": []})
    assert resp.status_code == 404


def test_recost_uses_active_card(client):
    client.post("/api/rate-cards", files={"file": ("onshore.csv", ONSHORE, "text/csv")}, data={"name": "Onshore"})
    created = client.post("/api/estimates", json={
        "project_name": "RAG", "prd_text": RAG_PRD,
        "client_context": {"tech_stack": ["Databricks"]},
    }).json()
    rc = client.post(f"/api/estimates/{created['estimate_id']}/recost")
    assert rc.status_code == 200, rc.text
    assert rc.json()["version"] == 2
