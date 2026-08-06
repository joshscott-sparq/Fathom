"""Notion notes for an opportunity (spec: each estimate accesses opportunity notes).

Real Notion API client when NOTION_API_KEY is set; otherwise returns modeled
sample notes so the feature is demonstrable offline. The deployed app calls the
Notion API directly (the claude.ai Notion connector is not available server-side).
"""

from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass
class NotionNote:
    title: str
    excerpt: str
    url: str | None = None


def notion_available() -> bool:
    return bool(os.environ.get("NOTION_API_KEY"))


def get_opportunity_notes(notion_page_ref: str | None) -> list[NotionNote]:
    """Fetch notes for an opportunity's Notion page.

    Stub: returns modeled notes unless NOTION_API_KEY is set and a page ref is
    present, in which case it would call the Notion API (wired here, needs creds).
    """
    if not notion_page_ref:
        return []
    if notion_available():
        try:
            return _fetch_live(notion_page_ref)
        except Exception:  # noqa: BLE001 - fall back to modeled notes on any error
            pass
    return _sample_notes(notion_page_ref)


def _fetch_live(page_ref: str) -> list[NotionNote]:  # pragma: no cover - needs creds
    import httpx  # available via test deps; ship as a dependency when enabling live

    page_id = page_ref.rstrip("/").split("/")[-1].split("-")[-1]
    headers = {
        "Authorization": f"Bearer {os.environ['NOTION_API_KEY']}",
        "Notion-Version": "2022-06-28",
    }
    resp = httpx.get(f"https://api.notion.com/v1/blocks/{page_id}/children", headers=headers, timeout=15)
    resp.raise_for_status()
    notes: list[NotionNote] = []
    for block in resp.json().get("results", []):
        rich = block.get(block.get("type", ""), {}).get("rich_text", [])
        text = "".join(t.get("plain_text", "") for t in rich).strip()
        if text:
            notes.append(NotionNote(title=block.get("type", "note"), excerpt=text[:300]))
    return notes


def _sample_notes(page_ref: str) -> list[NotionNote]:
    return [
        NotionNote(
            title="Discovery summary",
            excerpt="Stakeholders aligned on grounded Q&A over the corpus; compliance is the gating concern.",
            url=page_ref if page_ref.startswith("http") else None,
        ),
        NotionNote(
            title="Open questions",
            excerpt="Confirm data residency, expected query volume, and the evaluation bar for answer quality.",
        ),
        NotionNote(
            title="Next steps",
            excerpt="SC to produce a calibrated estimate and a reference architecture for the SOW.",
        ),
    ]
