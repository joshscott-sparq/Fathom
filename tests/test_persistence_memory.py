"""Contract: persistence versioning, retrieval, prior tuning, and the service."""

from fathom.memory.priors import ActualOutcome, tune_pattern_prior
from fathom.models.results import ClientContext
from fathom.data_loader import load_patterns
from fathom.persistence.store import SQLiteEstimateRepository
from fathom.service import EstimateService

RAG_PRD = "- retrieval augmented generation over knowledge base\n- embeddings vector store on databricks\n- grounded llm answers"
NET_PRD = "- modernize legacy .net monolith\n- strangler migration behind a gateway\n- extract services"


def test_versioning_creates_new_versions(tmp_path):
    repo = SQLiteEstimateRepository(tmp_path / "t.db")
    svc = EstimateService(repo=repo)
    stored, _ = svc.create_estimate("Acme", RAG_PRD, ClientContext(tech_stack=["Databricks"]))
    assert stored.version == 1

    graph = stored.graph
    graph.assumptions.append("edited by user")
    updated = svc.update_estimate(stored.estimate_id, graph)
    assert updated.version == 2
    assert repo.list_versions(stored.estimate_id) == [1, 2]
    # Old version still retrievable (audit trail).
    assert repo.get(stored.estimate_id, 1).version == 1
    assert repo.get(stored.estimate_id).version == 2  # latest


def test_retrieval_finds_same_pattern(tmp_path):
    svc = EstimateService(repo=SQLiteEstimateRepository(tmp_path / "t.db"))
    svc.create_estimate("Prior RAG", RAG_PRD, ClientContext(tech_stack=["Databricks", "Python"]))
    svc.create_estimate("Prior .NET", NET_PRD, ClientContext(tech_stack=[".NET"]))

    _, refs = svc.create_estimate("New RAG", RAG_PRD, ClientContext(tech_stack=["Databricks"]))
    assert refs, "expected reference-class matches"
    assert refs[0].project_name == "Prior RAG"
    assert "same pattern" in refs[0].why


def test_get_references_recomputes_on_open_not_just_create(tmp_path):
    """References aren't persisted on the graph — simply opening an estimate
    later must recompute them fresh, not just the moment it's created."""
    svc = EstimateService(repo=SQLiteEstimateRepository(tmp_path / "t.db"))
    svc.create_estimate("Prior RAG", RAG_PRD, ClientContext(tech_stack=["Databricks", "Python"]))
    stored, _ = svc.create_estimate("New RAG", RAG_PRD, ClientContext(tech_stack=["Databricks"]))

    refs = svc.get_references(stored.estimate_id)
    assert refs, "expected reference-class matches when reopening later"
    assert refs[0].project_name == "Prior RAG"
    # The estimate never references itself.
    assert all(r.estimate_id != stored.estimate_id for r in refs)


def test_prior_tuning_shrinks_toward_observed(tmp_path):
    repo = SQLiteEstimateRepository(tmp_path / "t.db")
    svc = EstimateService(repo=repo)
    # Seed a few RAG estimates.
    for i in range(3):
        svc.create_estimate(f"RAG {i}", RAG_PRD, ClientContext(tech_stack=["Databricks"]))

    patterns, _ = load_patterns()
    library = patterns["rag-databricks"].parametric_cost
    prior = tune_pattern_prior("rag-databricks", library, repo.all_latest())
    assert prior.sample_count == 3
    # Tuned base sits between library base and observed base.
    assert prior.observed_base is not None
    lo, hi = sorted([prior.library_base, prior.observed_base])
    assert lo <= prior.tuned_base <= hi


def test_actuals_take_priority_in_priors(tmp_path):
    repo = SQLiteEstimateRepository(tmp_path / "t.db")
    svc = EstimateService(repo=repo)
    stored, _ = svc.create_estimate("RAG live", RAG_PRD, ClientContext(tech_stack=["Databricks"]))
    svc.record_actuals(ActualOutcome(estimate_id=stored.estimate_id, delivered_points=999))

    patterns, _ = load_patterns()
    prior = tune_pattern_prior(
        "rag-databricks", patterns["rag-databricks"].parametric_cost,
        repo.all_latest(), svc._actuals,
    )
    assert prior.used_actuals == 1
    assert prior.observed_base == 999
