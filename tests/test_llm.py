"""Contract: LLM ingest/matching/capabilities via an injected fake client,
plus deterministic fallback. No network."""

from fathom.core import estimation, llm
from fathom.data_loader import load_estimate_kinds
from fathom.models.graph import EdgeKind
from fathom.models.results import ClientContext

RAG_PRD = "- grounded llm answers over our knowledge base\n- runs on databricks with a vector store"


class FakeLLM:
    """Routes by prompt content to canned structured replies."""

    def complete_json(self, system, user, *, max_tokens=4000):
        if "Existing requirements already captured" in user:
            return {"requirements": [
                {"text": "Grounded answers over the corpus", "kind": "functional", "confidence": 0.9},
                {"text": "Supports multi-turn conversation", "kind": "functional", "confidence": 0.8},
            ]}
        if "Extract the requirements" in user:
            return {"requirements": [
                {"text": "Grounded answers over the corpus", "kind": "functional", "confidence": 0.9},
                {"text": "Runs on Databricks", "kind": "constraint", "confidence": 0.8},
            ]}
        if "score each pattern" in user:
            return {"matches": [
                {"pattern_id": "rag-databricks", "score": 0.95, "rationale": "clear RAG on Databricks"},
                {"pattern_id": "agentic-mcp", "score": 0.1, "rationale": "not agentic"},
            ]}
        if "derive 3-7 capabilities" in user:
            return {
                "capabilities": [
                    {"name": "Knowledge Retrieval", "description": "Find relevant context"},
                    {"name": "Answer Generation", "description": "Produce grounded answers"},
                ],
                "requirement_links": [0, 1],
                "component_links": {"Vector Store": 0, "Retrieval Orchestrator": 1},
            }
        return {}


def test_parse_json_object_tolerates_prose():
    assert llm._parse_json_object('Sure! {"a": 1} done')["a"] == 1


def test_llm_extract_and_rank_and_capabilities_directly():
    fake = FakeLLM()
    reqs = llm.extract_requirements(RAG_PRD, client=fake)
    assert len(reqs) == 2 and reqs[0]["kind"] == "functional"

    ranked = llm.rank_patterns(RAG_PRD, ["Databricks"], [
        {"id": "rag-databricks", "name": "RAG", "when_to_use": "..."},
        {"id": "agentic-mcp", "name": "Agentic", "when_to_use": "..."},
    ], client=fake)
    assert ranked[0]["pattern_id"] == "rag-databricks"

    caps = llm.derive_capabilities(RAG_PRD, ["r1", "r2"], ["Vector Store"], client=fake)
    assert [c["name"] for c in caps["capabilities"]] == ["Knowledge Retrieval", "Answer Generation"]


def test_build_estimate_uses_llm_path_when_injected():
    graph = estimation.build_estimate(
        "LLM RAG", RAG_PRD, ClientContext(tech_stack=["Databricks"]),
        use_llm=True, llm_client=FakeLLM(),
    )
    assert graph.matched_pattern_ids == ["rag-databricks"]
    # Capabilities are the LLM's higher-level ones, not 1:1 component names.
    cap_names = {c.name for c in graph.capabilities}
    assert "Knowledge Retrieval" in cap_names
    # Requirements came from the LLM.
    assert any("Grounded answers" in r.text for r in graph.requirements)
    # Provenance recorded in assumptions.
    assert any("LLM" in a for a in graph.assumptions)
    # Graph integrity: every requirement/capability edge resolves (model validated).
    assert graph.edges_of_kind(EdgeKind.REALIZED_BY)


def test_build_estimate_falls_back_without_llm():
    graph = estimation.build_estimate(
        "Heuristic RAG", RAG_PRD, ClientContext(tech_stack=["Databricks"]), use_llm=False
    )
    assert graph.matched_pattern_ids == ["rag-databricks"]
    assert any("heuristic" in a for a in graph.assumptions)


def test_extract_new_requirements_tags_duplicates_via_safety_net():
    """Even if the model includes something already in `existing`, the
    word-overlap safety net tags it with its match rather than dropping it —
    only the genuinely new item comes back with duplicate_of=None."""
    fake = FakeLLM()
    existing = ["Grounded answers over the corpus documents"]
    new = llm.extract_new_requirements("some dropped document text", existing, client=fake)
    by_text = {r["text"]: r["duplicate_of"] for r in new}
    assert by_text == {
        "Grounded answers over the corpus": "Grounded answers over the corpus documents",
        "Supports multi-turn conversation": None,
    }


def test_heuristic_new_requirements_decomposes_and_tags_duplicates():
    text = "- Grounded answers over the corpus\n- Supports multi-turn conversation\n- x"
    existing = ["Grounded answers over the corpus"]
    new = llm.heuristic_new_requirements(text, existing)
    by_text = {r["text"]: r["duplicate_of"] for r in new}
    assert by_text == {
        "Grounded answers over the corpus": "Grounded answers over the corpus",
        "Supports multi-turn conversation": None,
    }
    # "- x" is too short (< 10 chars after stripping the bullet) to count.


def test_heuristic_new_requirements_skips_markdown_scaffolding():
    """A dropped PRD's title/headings/metadata must not each become their own
    fake "requirement" — only substantive lines should survive."""
    text = (
        "# Product Requirements Document: FleetOps Portal\n"
        "**Document status:** Draft for estimation\n"
        "**Version:** 0.9\n"
        "## 1. Overview\n"
        "FleetOps operates a mixed fleet of 450 vehicles across 12 regional depots.\n"
    )
    new = llm.heuristic_new_requirements(text, [])
    assert [r["text"] for r in new] == [
        "FleetOps operates a mixed fleet of 450 vehicles across 12 regional depots."
    ]


def test_summarize_document_heuristic_skips_markdown_scaffolding():
    text = (
        "# Product Requirements Document: FleetOps Portal\n"
        "**Document status:** Draft for estimation\n"
        "FleetOps operates a mixed fleet of 450 vehicles across 12 regional depots.\n"
        "We need a web and mobile application that centralizes preventive maintenance scheduling.\n"
    )
    summary = llm.heuristic_summarize(text)
    assert summary == (
        "- FleetOps operates a mixed fleet of 450 vehicles across 12 regional depots.\n"
        "- We need a web and mobile application that centralizes preventive maintenance scheduling."
    )


def test_find_duplicate_catches_paraphrases_by_word_overlap():
    assert llm._find_duplicate("Grounded answers over the corpus", ["The corpus grounds answers over"])
    assert llm._find_duplicate("Supports multi-turn conversation", ["Grounded answers over the corpus"]) is None


def test_summarize_document_heuristic_caps_at_max_items():
    text = "\n".join(f"This is a substantial requirement line number {i} of the document." for i in range(10))
    summary = llm.heuristic_summarize(text, max_items=3)
    assert summary.count("\n- ") == 2  # 3 bullets total: one leading "- " plus two "\n- "
    assert summary.startswith("- ")


def test_summarize_document_heuristic_falls_back_to_truncated_blob_when_nothing_substantive():
    summary = llm.heuristic_summarize("hi\nok\n")
    assert not summary.startswith("- ")


def test_summarize_document_uses_llm_bullets():
    class FakeSummaryLLM:
        def complete_json(self, system, user, *, max_tokens=4000):
            return {"bullets": [
                "Ingestion and embedding pipelines run on databricks with a managed vector store",
                "Evaluation harness measures answer quality and guards against regressions",
                "Web chat UI for the adjuster team with feedback capture",
            ]}

    summary = llm.summarize_document("some long document text", client=FakeSummaryLLM())
    assert summary == (
        "- Ingestion and embedding pipelines run on databricks with a managed vector store\n"
        "- Evaluation harness measures answer quality and guards against regressions\n"
        "- Web chat UI for the adjuster team with feedback capture"
    )


TAXONOMY, _ = load_estimate_kinds()


def test_classify_kind_uses_llm_and_falls_back_on_bad_kind():
    class FakeClassifyLLM:
        def complete_json(self, system, user, *, max_tokens=4000):
            return {"kind": "risk", "confidence": 0.9, "rationale": "expresses probability of harm"}

    result = llm.classify_kind("The vendor may fail to deliver the API on time.", TAXONOMY, client=FakeClassifyLLM())
    assert result["kind"] == "risk" and result["confidence"] == 0.9 and result["rationale"] == "expresses probability of harm"
    assert result["title"]  # falls back to a naive title when the model doesn't supply one

    class HallucinatingLLM:
        def complete_json(self, system, user, *, max_tokens=4000):
            return {"kind": "not-a-real-kind", "confidence": 0.9, "rationale": "..."}

    # An unrecognized kind name falls back to "feature", the taxonomy's
    # closest general "this is scope to build" kind — never surfaced raw.
    result = llm.classify_kind("something", TAXONOMY, client=HallucinatingLLM())
    assert result["kind"] == "feature"


def test_heuristic_classify_kind_matches_signals():
    cases = {
        "There is a risk the vendor may fail to deliver on time.": "risk",
        "We assume the client will supply test data by kickoff.": "assumption",
        "We have a reusable AI-assisted codegen framework for this.": "accelerator",
        "Discovery phase runs sprints 1-3.": "phase",
        "As a driver, I want to submit a DVIR so that compliance is tracked.": "story",
    }
    for text, expected in cases.items():
        assert llm.heuristic_classify_kind(text, TAXONOMY)["kind"] == expected, text


def test_heuristic_classify_kind_defaults_to_feature():
    result = llm.heuristic_classify_kind("Bulk CSV export of maintenance records.", TAXONOMY)
    assert result["kind"] == "feature"
    assert result["confidence"] < 0.4


def test_heuristic_classify_kind_avoids_short_signal_false_positives():
    """"SP" is a signal for story_point, but must word-boundary match — it
    shouldn't fire on ordinary words like "sprints" that merely contain it."""
    result = llm.heuristic_classify_kind("Discovery phase runs sprints 1-3.", TAXONOMY)
    assert result["kind"] != "story_point"


def test_classify_kind_routes_spec_iq_gap_to_assumption_without_calling_llm():
    class ExplodingLLM:
        def complete_json(self, system, user, *, max_tokens=4000):
            raise AssertionError("should not call the LLM for a skill-authored flag")

    result = llm.classify_kind("⚑  Gap: The budget cap for phase 2 is unclear", TAXONOMY, client=ExplodingLLM())
    assert result["kind"] == "assumption"
    assert result["confidence"] == 0.95
    assert result["title"] == "The budget cap for phase 2"


def test_classify_kind_routes_spec_iq_conflict_to_risk_without_calling_llm():
    class ExplodingLLM:
        def complete_json(self, system, user, *, max_tokens=4000):
            raise AssertionError("should not call the LLM for a skill-authored flag")

    result = llm.classify_kind(
        "⚠  Conflict: Stakeholder list says Q3 launch but timeline says Q4", TAXONOMY, client=ExplodingLLM()
    )
    assert result["kind"] == "risk"
    assert result["confidence"] == 0.95


def test_heuristic_classify_kind_routes_spec_iq_flags():
    gap = llm.heuristic_classify_kind("⚑  Gap: The budget cap for phase 2 is unclear", TAXONOMY)
    assert gap["kind"] == "assumption"
    conflict = llm.heuristic_classify_kind(
        "⚠  Conflict: Stakeholder list says Q3 launch but timeline says Q4", TAXONOMY
    )
    assert conflict["kind"] == "risk"


def test_group_into_epics_uses_llm_clustering():
    class FakeEpicLLM:
        def complete_json(self, system, user, *, max_tokens=4000):
            return {"epics": [
                {"index": 0, "epic": "RAG Ingestion Pipeline"},
                {"index": 1, "epic": "RAG Ingestion Pipeline"},
                {"index": 2, "epic": "Claims Search"},
            ]}

    texts = ["Ingestion pipeline on Databricks", "Embedding pipeline on Databricks", "Search prior claims"]
    epics = llm.group_into_epics(texts, client=FakeEpicLLM())
    assert epics == ["RAG Ingestion Pipeline", "RAG Ingestion Pipeline", "Claims Search"]


def test_heuristic_group_into_epics_is_not_filename_derived():
    """Without an LLM, real topic clustering isn't possible — but the
    fallback must still describe the extracted features, never the source
    document/filename they came from."""
    epics = llm.heuristic_group_into_epics(["a", "b", "c"])
    assert epics == ["Extracted Features", "Extracted Features", "Extracted Features"]
    assert all("." not in e and "/" not in e for e in epics)  # not a filename


def test_llm_step_falls_back_on_error():
    class Boom:
        def complete_json(self, *a, **k):
            raise RuntimeError("api down")

    # Should not raise; each LLM step falls back to the heuristic.
    graph = estimation.build_estimate(
        "Resilient", RAG_PRD, ClientContext(tech_stack=["Databricks"]),
        use_llm=True, llm_client=Boom(),
    )
    assert graph.requirements and graph.capabilities
    assert any("heuristic" in a for a in graph.assumptions)
