"""LLM ingest and matching (spec §3.1-3.3), Anthropic-backed with fallback.

Three capabilities, each with a deterministic fallback so the engine runs offline:
- `extract_requirements`  — structured requirements from a PRD (vs line-based).
- `derive_capabilities`   — real higher-level capabilities and their links (vs 1:1).
- `rank_patterns`         — nuanced pattern match (vs signal-overlap scoring).

The client is injectable (`LLMClient` protocol) so the parsing/integration logic
is testable with a fake client and no network. `available()` reports whether a
real call is possible; callers fall back to heuristics when it is not, or on any
error. Structured replies are requested as JSON and defensively parsed.
"""

from __future__ import annotations

import json
import os
import re
from typing import Protocol

from ..models.kinds import KindTaxonomy

# Latest Claude model suited to extraction/reasoning at good latency/cost.
# Override with FATHOM_LLM_MODEL.
DEFAULT_MODEL = "claude-sonnet-5"


class LLMClient(Protocol):
    def complete_json(self, system: str, user: str, *, max_tokens: int = 4000) -> dict: ...


def model_name() -> str:
    return os.environ.get("FATHOM_LLM_MODEL", DEFAULT_MODEL)


def available() -> bool:
    """True when a real Anthropic call is possible.

    Requires ANTHROPIC_API_KEY and that FATHOM_DISABLE_LLM is not set (an
    escape hatch to force the deterministic path even when a key is present).
    """
    if os.environ.get("FATHOM_DISABLE_LLM", "").strip().lower() in {"1", "true", "yes"}:
        return False
    return bool(os.environ.get("ANTHROPIC_API_KEY"))


class AnthropicClient:
    """Real client. Asks for a JSON object and parses it defensively."""

    def __init__(self, model: str | None = None):
        self.model = model or model_name()

    def complete_json(self, system: str, user: str, *, max_tokens: int = 4000) -> dict:
        import anthropic

        client = anthropic.Anthropic()
        message = client.messages.create(
            model=self.model,
            max_tokens=max_tokens,
            system=system + "\n\nRespond with a single valid JSON object and nothing else.",
            messages=[{"role": "user", "content": user}],
        )
        text = "".join(b.text for b in message.content if getattr(b, "type", None) == "text")
        return _parse_json_object(text)


def _parse_json_object(text: str) -> dict:
    """Extract and parse the first JSON object from a model reply."""
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if not match:
        raise ValueError("no JSON object found in model reply")
    return json.loads(match.group(0))


def _client(client: LLMClient | None) -> LLMClient:
    return client or AnthropicClient()


def extract_requirements(prd_text: str, *, client: LLMClient | None = None) -> list[dict]:
    """Return [{text, kind, confidence}] extracted from the PRD.

    kind is one of functional/non_functional/constraint; confidence is 0-1.
    """
    system = (
        "You are a senior delivery lead extracting requirements from a PRD for "
        "estimation. Consolidate bullets/prose into distinct, atomic requirements."
    )
    user = (
        "Extract the requirements from the following PRD. For each, give the text, "
        "a kind (functional | non_functional | constraint), and a confidence 0-1 "
        "reflecting how clearly the PRD states it.\n\n"
        'Return JSON: {"requirements": [{"text": str, "kind": str, "confidence": number}]}\n\n'
        f"PRD:\n{prd_text}"
    )
    data = _client(client).complete_json(system, user)
    return _parse_requirement_items(data)


def _parse_requirement_items(data: dict) -> list[dict]:
    out: list[dict] = []
    for r in data.get("requirements", []):
        text = str(r.get("text", "")).strip()
        if not text:
            continue
        kind = str(r.get("kind", "functional")).strip().lower()
        if kind not in {"functional", "non_functional", "constraint"}:
            kind = "functional"
        conf = r.get("confidence", 0.7)
        out.append({"text": text[:300], "kind": kind, "confidence": _clamp(conf)})
    return out


def _normalize_words(text: str) -> set[str]:
    return set(re.findall(r"[a-z0-9]+", text.lower()))


def _find_duplicate(candidate: str, existing: list[str], threshold: float = 0.6) -> str | None:
    """Word-overlap heuristic: return the existing entry `candidate` substantially
    restates (paraphrase or near-duplicate), or None if it looks distinct."""
    cand_words = _normalize_words(candidate)
    if not cand_words:
        return None
    for e in existing:
        e_words = _normalize_words(e)
        if not e_words:
            continue
        overlap = len(cand_words & e_words) / len(cand_words | e_words)
        if overlap >= threshold:
            return e
    return None


def extract_new_requirements(text: str, existing: list[str], *, client: LLMClient | None = None) -> list[dict]:
    """Decompose `text` (a dropped file or fetched URL) into atomic requirements —
    e.g. what's already in the Context Panel's Requirements tab.

    Same [{text, kind, confidence}] shape as `extract_requirements`, plus
    `duplicate_of`: the existing entry text this substantially restates, or None
    if it looks like a genuinely new requirement. Callers group a duplicate with
    its match and flag it rather than silently dropping it — a word-overlap
    check runs even on the LLM path, in case a near-duplicate slips through.
    """
    existing_block = "\n".join(f"- {e}" for e in existing) if existing else "(none yet)"
    system = (
        "You are a senior delivery lead adding to an existing requirements list from a "
        "newly dropped document. Decompose the document into distinct, atomic requirements. "
        "Ignore document scaffolding — titles, section headings, and metadata fields like "
        "status/version/prepared-for — those are not requirements. "
        "The existing list is shown for context only — a separate process handles duplicate "
        "detection, so include EVERY requirement the document states, even ones that look "
        "similar to or already covered by the existing list. Do not omit anything yourself."
    )
    user = (
        f"Existing requirements already captured (context only — do not omit matches "
        f"yourself):\n{existing_block}\n\n"
        "Extract every requirement stated in the following document, including ones "
        "similar to the existing list above. For each, give the text, a kind "
        "(functional | non_functional | constraint), and a confidence 0-1.\n\n"
        'Return JSON: {"requirements": [{"text": str, "kind": str, "confidence": number}]}\n\n'
        f"Document:\n{text}"
    )
    data = _client(client).complete_json(system, user)
    items = _parse_requirement_items(data)
    for it in items:
        it["duplicate_of"] = _find_duplicate(it["text"], existing)
    return items


_BULLET = re.compile(r"^\s*(?:[-*•]|\d+[.)])\s+")
# Markdown structure that is never itself a requirement — a heading (# / ##)
# or a document-metadata line (**Status:** Draft, **Version:** 0.9, ...).
# Without filtering these, a dropped PRD's front matter explodes into one
# junk "requirement" per heading/label instead of the real content.
_HEADER = re.compile(r"^\s*#{1,6}\s+")
_METADATA_LABEL = re.compile(r"^\s*\*\*[^*\n]+:\*\*")


def _is_structural_noise(line: str) -> bool:
    return bool(_HEADER.match(line) or _METADATA_LABEL.match(line))


def heuristic_new_requirements(text: str, existing: list[str], max_items: int = 60) -> list[dict]:
    """Deterministic fallback for extract_new_requirements: line-split + tag duplicates.

    Skips markdown headings and metadata lines (title, status, version, ...)
    so document scaffolding doesn't masquerade as a requirement.
    """
    out: list[dict] = []
    for line in text.splitlines():
        if _is_structural_noise(line):
            continue
        stripped = _BULLET.sub("", line).strip()
        if len(stripped) < 10:
            continue
        out.append({
            "text": stripped[:300], "kind": "functional", "confidence": 0.5,
            "duplicate_of": _find_duplicate(stripped, existing),
        })
        if len(out) >= max_items:
            break
    return out


def summarize_document(text: str, *, client: LLMClient | None = None) -> str:
    """A 2-5 bullet summary of a dropped document's key requirements/features,
    shown as the content of the Requirements-tab entry for the file itself
    (distinct from the decomposed requirement entries it also produces). One
    requirement/feature per bullet, "- " prefixed, e.g.:
        - Ingestion and embedding pipelines run on databricks with a managed vector store
        - Evaluation harness measures answer quality and guards against regressions
    """
    system = (
        "You are a senior delivery lead. Summarize the following document as 2-5 "
        "concise bullet points capturing its key requirements or features, for a "
        "teammate skimming a requirements list. One requirement or feature per bullet."
    )
    user = (
        f"Document:\n{text[:8000]}\n\n"
        'Return JSON: {"bullets": [str, str, ...]} with 2 to 5 items.'
    )
    data = _client(client).complete_json(system, user)
    bullets = [str(b).strip() for b in data.get("bullets", []) if str(b).strip()][:5]
    return "\n".join(f"- {b}" for b in bullets)


def heuristic_summarize(text: str, max_items: int = 5) -> str:
    """Deterministic fallback for summarize_document: up to `max_items` of the
    document's substantive lines (skipping markdown headings/metadata),
    formatted as bullets. Falls back to a single truncated line if nothing
    substantive is found.
    """
    bullets: list[str] = []
    for line in text.splitlines():
        if _is_structural_noise(line):
            continue
        stripped = _BULLET.sub("", line).strip()
        if len(stripped) < 30:
            continue
        bullets.append(_truncate(stripped, 200))
        if len(bullets) >= max_items:
            break
    if not bullets:
        return _truncate(" ".join(text.split()), 240)
    return "\n".join(f"- {b}" for b in bullets)


def _truncate(s: str, max_len: int) -> str:
    if len(s) <= max_len:
        return s
    return s[:max_len].rsplit(" ", 1)[0] + "…"


def _kind_prompt_block(taxonomy: KindTaxonomy) -> str:
    lines: list[str] = []
    for k in taxonomy.kinds:
        lines.append(f"- {k.name} ({k.role}): {k.definition.strip()}")
        for d in k.disambiguation:
            lines.append(f"  vs {d.against}: {d.distinction.strip()}")
        if k.signals:
            lines.append(f"  signals: {'; '.join(k.signals)}")
    return "\n".join(lines)


def classify_kind(text: str, taxonomy: KindTaxonomy, *, client: LLMClient | None = None) -> dict:
    """Classify `text` (one extracted sentence/line) against the estimate-kind
    taxonomy (data/estimate_kinds.yaml) — is it an epic, feature, story,
    story_point, risk, assumption, accelerator, or phase?

    Also returns a short `title` (3-6 words) distinct from the full `text` —
    callers use the title as the work-item's short name (grid cell) and keep
    the full sentence as its notes, so detail from the source document isn't
    lost just because the grid shows a terse label.

    Returns {"kind": str, "confidence": float, "rationale": str, "title": str}.
    `kind` is always one of taxonomy.names(); if the model returns something
    else (hallucinated name, refusal, etc.), it falls back to "feature" — the
    taxonomy's closest general "this is scope to build" kind.
    """
    names = taxonomy.names()
    system = (
        "You are a senior delivery lead filing a piece of text pulled from a source "
        "document into the correct part of a project estimate. Classify it against "
        "exactly one of the following kinds, using each kind's definition and its "
        "pairwise distinctions to resolve ambiguity (the same underlying work item can "
        "carry both an epic and a phase — they are not mutually exclusive):\n\n"
        + _kind_prompt_block(taxonomy)
    )
    user = (
        f"Text to classify:\n{text}\n\n"
        f'Return JSON: {{"kind": one of {names}, "confidence": number 0-1, "rationale": str, '
        '"title": a short 3-6 word name for this item, distinct from the full text}'
    )
    data = _client(client).complete_json(system, user)
    kind = str(data.get("kind", "")).strip()
    if kind not in names:
        kind = "feature"
    title = str(data.get("title", "")).strip() or _naive_title(text)
    return {
        "kind": kind,
        "confidence": _clamp(data.get("confidence", 0.5)),
        "rationale": str(data.get("rationale", "")).strip(),
        "title": title,
    }


def _naive_title(text: str, max_words: int = 6, max_len: int = 60) -> str:
    """Heuristic short title: the first few words of `text`, trimmed of
    boilerplate lead-ins ("The system must ...", "We need ...") that would
    otherwise dominate every title."""
    stripped = re.sub(
        r"^\s*(the system (shall|must|will)|we need( to)?|the system should)\s+",
        "", text.strip(), flags=re.IGNORECASE,
    ).strip()
    words = stripped.split()
    title = " ".join(words[:max_words])
    title = _truncate(title, max_len).rstrip(".")
    return title[:1].upper() + title[1:] if title else text[:max_len]


_USER_STORY_PATTERN = re.compile(r"^\s*as an?\s+.+?,?\s+i\s+want\b", re.IGNORECASE)


def heuristic_classify_kind(text: str, taxonomy: KindTaxonomy) -> dict:
    """Deterministic fallback for classify_kind: score each kind by how many of
    its signal phrases appear (case-insensitive, word-boundary matched) in
    `text`, picking the highest-scoring kind. Descriptive (non-literal)
    signals simply never match, which is harmless — they just don't
    contribute to the score. Defaults to "feature" when nothing scores above
    zero. The "As a ... I want ..." story template is checked explicitly
    first since its literal taxonomy signal is a placeholder, not real text
    to substring-match against.
    """
    title = _naive_title(text)
    if _USER_STORY_PATTERN.search(text):
        return {"kind": "story", "confidence": 0.7, "rationale": "matches the user-story template", "title": title}
    lowered = text.lower()
    best_kind = "feature"
    best_score = 0
    for k in taxonomy.kinds:
        score = 0
        for signal in k.signals:
            pattern = r"\b" + re.escape(signal.lower()) + r"\b"
            if re.search(pattern, lowered):
                score += 1
        if score > best_score:
            best_score = score
            best_kind = k.name
    return {
        "kind": best_kind,
        "confidence": 0.4 if best_score else 0.2,
        "rationale": "keyword match" if best_score else "no signals matched; defaulted to feature",
        "title": title,
    }


def group_into_epics(feature_texts: list[str], *, client: LLMClient | None = None) -> list[str]:
    """Assign an epic (a short 2-6 word capability/theme name) to each item in
    `feature_texts`, grouping related items under the same epic. Returns one
    epic name per input, aligned by index.

    This is a single batched call over the whole set rather than part of
    classify_kind, because grouping is inherently cross-item — classifying
    one sentence at a time can't know that "Ingestion pipeline" and "Embedding
    pipeline" belong together, so per-item epic names would fragment instead
    of clustering. The epic must relate to what the features actually are
    about, not to the source document/filename they were extracted from.
    """
    if not feature_texts:
        return []
    numbered = "\n".join(f"{i}: {t}" for i, t in enumerate(feature_texts))
    system = (
        "You are a senior delivery lead organizing a flat list of features/stories into "
        "epics. Group related items under the same short epic name (2-6 words, a "
        "capability or theme, e.g. 'RAG Ingestion Pipeline', 'Claims Search'). An epic "
        "must describe what the grouped features are about — never the name of a "
        "source document or file. Every item needs an epic, including ones that stand alone."
    )
    user = (
        f"Items (index: text):\n{numbered}\n\n"
        'Return JSON: {"epics": [{"index": int, "epic": str}, ...]} — one entry per item above.'
    )
    data = _client(client).complete_json(system, user)
    by_index = {int(e["index"]): str(e["epic"]).strip() for e in data.get("epics", []) if "index" in e}
    return [by_index.get(i) or heuristic_group_into_epics(feature_texts)[i] for i in range(len(feature_texts))]


def heuristic_group_into_epics(feature_texts: list[str]) -> list[str]:
    """Deterministic fallback for group_into_epics. Real topic clustering
    needs an LLM; without one, every item from the same batch shares one
    generic epic — still related to the extracted features (not the source
    filename), just not sub-grouped by theme."""
    return ["Extracted Features" for _ in feature_texts]


def rank_patterns(
    prd_text: str,
    tech_stack: list[str],
    patterns: list[dict],
    *,
    client: LLMClient | None = None,
) -> list[dict]:
    """Return [{pattern_id, score, rationale}] ranked best-first.

    `patterns` is [{id, name, when_to_use}]. Scores are 0-1.
    """
    catalog = "\n".join(f"- {p['id']}: {p['name']} — {p.get('when_to_use', '')}" for p in patterns)
    system = "You are a solutions architect matching a PRD to a reference architecture pattern."
    user = (
        "Given the PRD, client tech stack, and the candidate patterns, score each "
        "pattern 0-1 for fit and give a one-line rationale.\n\n"
        'Return JSON: {"matches": [{"pattern_id": str, "score": number, "rationale": str}]}\n\n'
        f"Tech stack: {', '.join(tech_stack) or 'unspecified'}\n\n"
        f"Patterns:\n{catalog}\n\nPRD:\n{prd_text}"
    )
    data = _client(client).complete_json(system, user)
    valid_ids = {p["id"] for p in patterns}
    out = [
        {"pattern_id": m["pattern_id"], "score": _clamp(m.get("score", 0)), "rationale": str(m.get("rationale", ""))}
        for m in data.get("matches", [])
        if m.get("pattern_id") in valid_ids
    ]
    out.sort(key=lambda m: m["score"], reverse=True)
    return out


def derive_capabilities(
    prd_text: str,
    requirement_texts: list[str],
    component_names: list[str],
    *,
    client: LLMClient | None = None,
) -> dict:
    """Derive higher-level capabilities and their links.

    Returns {capabilities: [{name, description}],
             requirement_links: [cap_index per requirement],
             component_links: {component_name: cap_index}}.
    """
    system = (
        "You are a business architect. Capabilities are what the system must be "
        "able to do, at a higher level than individual requirements or components."
    )
    user = (
        "From the PRD, requirements, and the proposed architecture components, "
        "derive 3-7 capabilities. Then map each requirement (by its index) to the "
        "capability it belongs to, and each component (by name) to the capability "
        "it realizes.\n\n"
        'Return JSON: {"capabilities": [{"name": str, "description": str}], '
        '"requirement_links": [int, ...], "component_links": {"<component name>": int}}\n\n'
        f"Requirements (indexed):\n"
        + "\n".join(f"{i}. {t}" for i, t in enumerate(requirement_texts))
        + f"\n\nComponents: {', '.join(component_names)}\n\nPRD:\n{prd_text}"
    )
    data = _client(client).complete_json(system, user)
    caps = [
        {"name": str(c.get("name", "")).strip(), "description": str(c.get("description", "")).strip()}
        for c in data.get("capabilities", [])
        if str(c.get("name", "")).strip()
    ]
    if not caps:
        raise ValueError("no capabilities derived")
    return {
        "capabilities": caps,
        "requirement_links": data.get("requirement_links", []),
        "component_links": data.get("component_links", {}),
    }


def suggest_team_models(
    context_summary: str,
    dev_models: list[str],
    history_summary: str,
    *,
    client: LLMClient | None = None,
) -> list[dict]:
    """Propose scenarios optimized to be cheaper or faster, grounded in history.

    Returns [{goal, name, dev_model, location_mix, engineers, rationale}].
    """
    system = (
        "You are a delivery strategist proposing alternative staffing/development "
        "models for a software estimate. Ground proposals in how similar past "
        "engagements actually performed when that history is provided."
    )
    user = (
        "Propose 2-4 scenarios, each optimized to be either cheaper or faster than "
        "the baseline, using the available development models and a location mix "
        "(US onshore, NS nearshore). Give each a short name, the dev_model, a "
        "location_mix (weights summing to 1), an optional engineers count, and a "
        "one-line rationale.\n\n"
        'Return JSON: {"suggestions": [{"goal": "cheaper|faster", "name": str, '
        '"dev_model": str, "location_mix": {"US": number, "NS": number}, '
        '"engineers": number|null, "rationale": str}]}\n\n'
        f"Available dev models: {', '.join(dev_models)}\n\n"
        f"Estimate summary:\n{context_summary}\n\n"
        f"Relevant history:\n{history_summary or 'none'}"
    )
    data = _client(client).complete_json(system, user)
    return data.get("suggestions", [])


def suggest_deferrals(work_items_summary: str, *, client: LLMClient | None = None) -> list[dict]:
    """Suggest features to defer to a later version to reduce time.

    Returns [{feature, rationale}] naming features from the provided list.
    """
    system = (
        "You are a product strategist identifying scope that could move to a later "
        "release to shorten the first delivery, preferring non-core or cross-cutting work."
    )
    user = (
        "From the feature list, suggest which to defer to a future version to cut "
        "delivery time, with a one-line rationale each. Only name features from the list.\n\n"
        'Return JSON: {"deferrals": [{"feature": str, "rationale": str}]}\n\n'
        f"Features:\n{work_items_summary}"
    )
    data = _client(client).complete_json(system, user)
    return data.get("deferrals", [])


def _clamp(value, lo: float = 0.0, hi: float = 1.0) -> float:
    try:
        return max(lo, min(hi, float(value)))
    except (TypeError, ValueError):
        return 0.5
