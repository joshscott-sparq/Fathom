"""Contract: demo seeding, PDF extraction, image-drop fallback."""

import io

import pytest
from fastapi.testclient import TestClient

from fathom.demo import DEMO_SCENARIOS, is_seeded, seed_demo
from fathom.persistence.store import SQLiteEstimateRepository
from fathom.service import EstimateService


@pytest.fixture()
def client(tmp_path, monkeypatch):
    from conftest import build_client

    return build_client(tmp_path, monkeypatch, role="admin")


def test_seed_demo_covers_all_patterns(tmp_path):
    svc = EstimateService(repo=SQLiteEstimateRepository(tmp_path / "d.db"))
    assert not is_seeded(svc)
    summary = seed_demo(svc)
    assert summary["created_count"] == len(DEMO_SCENARIOS)
    assert is_seeded(svc)

    # All three patterns represented (distinct architectures/diagrams).
    patterns = {p for e in svc.repo.all_latest() for p in e.graph.matched_pattern_ids}
    assert {"rag-databricks", "dotnet-modernization", "agentic-mcp"} <= patterns

    # Idempotent: re-seed creates nothing new.
    assert seed_demo(svc)["created_count"] == 0


def test_seed_demo_produces_versioned_and_referenced(tmp_path):
    svc = EstimateService(repo=SQLiteEstimateRepository(tmp_path / "d.db"))
    seed_demo(svc)
    latest = {e.graph.project_name: e for e in svc.repo.all_latest()}
    # The .NET scenario was recomputed -> v2.
    corom = latest["[Demo] Corom Manufacturing — Legacy .NET Modernization"]
    assert corom.version == 2


def test_seed_demo_populates_context_panel(tmp_path):
    """The lead estimate demonstrates every Context Panel tab with sample data."""
    svc = EstimateService(repo=SQLiteEstimateRepository(tmp_path / "d.db"))
    summary = seed_demo(svc)
    lead = svc.get_estimate(summary["created"][0]["estimate_id"])
    panel = lead.graph.context_panel
    assert len(panel.requirements) >= 2
    assert len(panel.risks) >= 1
    assert len(panel.accelerators) >= 1
    assert len(panel.assumptions) >= 1
    assert len(panel.phases) >= 3
    # External sources cover both a connected and a needs-auth state.
    statuses = {s.status.value for s in panel.external_sources}
    assert "connected" in statuses and "needs_authentication" in statuses
    # A Salesforce source is wired to the opportunity's real ids.
    sf = next(s for s in panel.external_sources if s.type.value == "salesforce")
    assert sf.config.get("opportunity")
    # Risks fed the estimation factors; the assumption was recorded.
    assert any(f.family.startswith("Risk:") for f in lead.graph.complexity_factors)
    assert any(a.startswith("Assumption: Client provisions") for a in lead.graph.assumptions)


def test_demo_endpoints(client):
    assert client.get("/api/demo/status").json()["seeded"] is False
    seeded = client.post("/api/demo/seed").json()
    assert seeded["created_count"] == len(DEMO_SCENARIOS)
    status = client.get("/api/demo/status").json()
    assert status["seeded"] is True and status["count"] >= len(DEMO_SCENARIOS)


def test_extract_pdf(client):
    # A valid (text-less) PDF authored via pypdf. Exercises the parse path and the
    # scanned/no-text fallback note.
    from pypdf import PdfWriter

    writer = PdfWriter()
    writer.add_blank_page(width=612, height=792)
    buf = io.BytesIO()
    writer.write(buf)

    resp = client.post("/api/context/extract", files={"file": ("reqs.pdf", buf.getvalue(), "application/pdf")})
    assert resp.status_code == 200, resp.text
    assert "no extractable text" in resp.json()["text"]


def test_decompose_requirements_tags_duplicates_against_existing(client):
    text = "- Grounded answers over the corpus\n- Supports multi-turn conversation\n- x"
    resp = client.post("/api/context/decompose-requirements", json={
        "text": text, "existing": ["Grounded answers over the corpus"],
    })
    assert resp.status_code == 200, resp.text
    items = resp.json()
    by_text = {it["text"]: it["duplicate_of"] for it in items}
    assert by_text == {
        "Grounded answers over the corpus": "Grounded answers over the corpus",
        "Supports multi-turn conversation": None,
    }


def test_decompose_requirements_includes_taxonomy_classification(client):
    """Each decomposed item is also classified against the estimate-kind
    taxonomy (D25) so the caller can route a real feature/epic/story into the
    estimate's work breakdown instead of the plain Requirements list."""
    text = "- As a driver, I want to submit a DVIR so that compliance is tracked."
    resp = client.post("/api/context/decompose-requirements", json={"text": text, "existing": []})
    assert resp.status_code == 200, resp.text
    items = resp.json()
    assert items and all("taxonomy_kind" in it and "taxonomy_confidence" in it for it in items)
    assert items[0]["taxonomy_kind"] == "story"
    # title/epic (D25 follow-up): a short name distinct from the full text,
    # and a grouping epic that describes the feature, not the source file.
    assert items[0]["title"] and items[0]["title"] != items[0]["text"]
    assert items[0]["epic"] and "." not in items[0]["epic"]


def test_decompose_requirements_empty_text(client):
    resp = client.post("/api/context/decompose-requirements", json={"text": "   ", "existing": []})
    assert resp.status_code == 200
    assert resp.json() == []


def test_summarize_document(client):
    text = "This document describes a system. " * 20
    resp = client.post("/api/context/summarize", json={"text": text})
    assert resp.status_code == 200, resp.text
    summary = resp.json()["summary"]
    assert summary
    assert len(summary) < len(text)


def test_summarize_document_empty_text(client):
    resp = client.post("/api/context/summarize", json={"text": "   "})
    assert resp.status_code == 200
    assert resp.json() == {"summary": ""}


def test_extract_pdf_rejects_garbage(client):
    resp = client.post("/api/context/extract", files={"file": ("bad.pdf", b"not a pdf", "application/pdf")})
    assert resp.status_code == 422


def test_extract_image_fallback_without_key(client):
    # 1x1 transparent PNG.
    png = bytes.fromhex(
        "89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c4"
        "890000000d49444154789c6360000002000100ffff03000006000557bfabd400"
        "00000049454e44ae426082"
    )
    resp = client.post("/api/context/extract", files={"file": ("arch.png", png, "image/png")})
    assert resp.status_code == 200, resp.text
    # No API key in this test -> graceful placeholder, not an error.
    assert "ANTHROPIC_API_KEY" in resp.json()["text"]
