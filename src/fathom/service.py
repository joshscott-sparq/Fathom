"""Application service: ties the engine, persistence, and memory together.

The API and CLI call this rather than reaching into layers directly. It applies
memory (tuned priors + reference-class retrieval) on the way in, persists the
result on the way out, and keeps in-memory actuals for calibration.
"""

from __future__ import annotations

from pathlib import Path

from . import data_loader
from .core import advisor, estimation
from .core.rates import RateCard, recost
from .core.scenarios import compute_scenarios, default_scenarios
from .memory.priors import ActualOutcome, tune_pattern_prior
from .memory.retrieval import Reference, find_references
from .models.results import ClientContext
from .models.scenario import DeferralSuggestion, Scenario, TeamSuggestion
from .models.solution_graph import SolutionGraph
from .models.team import RateRow
from .persistence.directory import SQLiteDirectoryRepository
from .persistence.rate_cards import SavedRateCard, SQLiteRateCardRepository
from .persistence.store import EstimateRepository, SQLiteEstimateRepository, StoredEstimate


class EstimateService:
    def __init__(self, repo: EstimateRepository | None = None, db_path: str | Path = "fathom.db"):
        self.repo = repo or SQLiteEstimateRepository(db_path)
        # Actuals held in-process for now; a table lands with the Phase 4 loop.
        self._actuals: dict[str, ActualOutcome] = {}
        resolved_db = getattr(self.repo, "db_path", db_path)
        # Persisted rate cards share the estimate database (one active, one default).
        self.rate_cards = SQLiteRateCardRepository(resolved_db)
        # Users, accounts, opportunities, assignments, shares, links, comments.
        self.directory = SQLiteDirectoryRepository(resolved_db)

    def active_rates(self) -> tuple[list[RateRow], str]:
        """The rate rows in effect (from the active card) and a source label."""
        card = self.rate_cards.active_card()
        return card.rows, card.name

    # --- Rate-card management ---

    def list_rate_cards(self) -> list[SavedRateCard]:
        return self.rate_cards.list_cards()

    def create_rate_card(self, name: str, rows: list[RateRow]) -> SavedRateCard:
        return self.rate_cards.create(name, rows, activate=True)

    def activate_rate_card(self, card_id: str) -> SavedRateCard:
        return self.rate_cards.activate(card_id)

    def update_rate_card(self, card_id: str, rows: list[RateRow]) -> SavedRateCard:
        return self.rate_cards.update_rows(card_id, rows)

    def delete_rate_card(self, card_id: str) -> None:
        self.rate_cards.delete(card_id)

    def recost_estimate(self, estimate_id: str) -> StoredEstimate:
        """Reprice an estimate under the active rate card; persist a new version."""
        stored = self.repo.get(estimate_id)
        if stored is None:
            raise KeyError(f"estimate {estimate_id!r} not found")
        rows, _ = self.active_rates()
        repriced = recost(stored.graph, RateCard(rows))
        return self.repo.update(estimate_id, repriced)

    def _build_graph(self, project_name, prd_text, context, match_override=None, context_panel=None, use_llm=None):
        """Build a graph with memory-tuned priors; returns (graph, references)."""
        context = context or ClientContext()
        patterns, _ = data_loader.load_patterns()
        past = self.repo.all_latest()

        preview_matches = estimation.score_patterns(prd_text, context, patterns)
        chosen_id = match_override or (preview_matches[0].pattern_id if preview_matches else None)
        parametric_override = None
        if chosen_id and chosen_id in patterns:
            prior = tune_pattern_prior(chosen_id, patterns[chosen_id].parametric_cost, past, self._actuals)
            if prior.sample_count > 0:
                parametric_override = prior.as_parametric(patterns[chosen_id].parametric_cost)

        rates, _ = self.active_rates()
        graph = estimation.build_estimate(
            project_name, prd_text, context,
            match_override=match_override, parametric_override=parametric_override, rates=rates,
            context_panel=context_panel, use_llm=use_llm,
        )
        references = find_references(prd_text, context, graph.matched_pattern_ids, past)
        return graph, references

    def recalculate_from_context(
        self, estimate_id: str, panel, use_llm: bool | None = None,
    ) -> tuple[StoredEstimate, list[Reference]]:
        """Save the Context Panel and re-estimate from it (auto-recalc, in place).

        Requirements entries form the PRD; risks/accelerators/assumptions and
        phases flow through the build. Tags are preserved. `panel.pinned_work_items`
        (D25: items classified from a just-dropped document) are re-appended to
        the rebuilt work_items on *every* call, not just the one that added
        them — recalculate_from_context always rebuilds work_items from scratch,
        so a one-shot append would get silently discarded the next time any
        other Context Panel edit triggers this same auto-recalc.
        """
        stored = self.repo.get(estimate_id)
        if stored is None:
            raise KeyError(f"estimate {estimate_id!r} not found")
        prd = "\n".join(e.content for e in panel.requirements if e.content.strip()).strip()
        if not prd:
            # No Requirements entries yet: preserve the estimate's existing scope
            # so editing only risks/assumptions doesn't wipe the breakdown.
            prd = "\n".join(f"- {r.text}" for r in stored.graph.requirements) or "(no requirements yet)"
        graph, references = self._build_graph(stored.graph.project_name, prd, stored.graph.client_context, context_panel=panel, use_llm=use_llm)
        graph.tags = list(stored.graph.tags)
        if panel.pinned_work_items:
            graph.work_items = [*graph.work_items, *panel.pinned_work_items]
        saved = self.repo.overwrite_latest(estimate_id, graph)
        return saved, references

    def create_estimate(
        self,
        project_name: str,
        prd_text: str,
        context: ClientContext | None = None,
        match_override: str | None = None,
        owner_id: str | None = None,
        opportunity_id: str | None = None,
        use_llm: bool | None = None,
    ) -> tuple[StoredEstimate, list[Reference]]:
        """Build with memory-tuned priors, persist, and return with references."""
        graph, references = self._build_graph(project_name, prd_text, context, match_override, use_llm=use_llm)
        stored = self.repo.create(graph, owner_id=owner_id, opportunity_id=opportunity_id)
        # First estimate on an opportunity becomes its active/official one.
        if opportunity_id:
            opp = self.directory.get_opportunity(opportunity_id)
            if opp and not opp.active_estimate_id:
                self.directory.set_active_estimate(opportunity_id, stored.estimate_id)
        return stored, references

    def rebuild_estimate(
        self,
        estimate_id: str,
        project_name: str,
        prd_text: str,
        context: ClientContext | None = None,
        opportunity_id: str | None = None,
    ) -> tuple[StoredEstimate, list[Reference]]:
        """Re-derive an estimate from updated inputs and auto-save in place."""
        if self.repo.get(estimate_id) is None:
            raise KeyError(f"estimate {estimate_id!r} not found")
        graph, references = self._build_graph(project_name, prd_text, context)
        stored = self.repo.overwrite_latest(estimate_id, graph)
        if opportunity_id:
            self.repo.set_opportunity(estimate_id, opportunity_id)
            opp = self.directory.get_opportunity(opportunity_id)
            if opp and not opp.active_estimate_id:
                self.directory.set_active_estimate(opportunity_id, estimate_id)
        return stored, references

    def clone_estimate(self, estimate_id: str, owner_id: str | None = None) -> StoredEstimate:
        """Copy an estimate to test other assumptions (new estimate, not active)."""
        return self.repo.clone(estimate_id, owner_id=owner_id)

    def share_principal_email(self, principal: str) -> str:
        """Resolve a share target given by email or by a known user's name."""
        principal = principal.strip()
        if "@" in principal:
            return principal.lower()
        match = next((u for u in self.directory.list_users() if u.name.lower() == principal.lower()), None)
        if match:
            return match.email
        raise ValueError(f"no user found named {principal!r}; share by email instead")

    def get_estimate(self, estimate_id: str, version: int | None = None) -> StoredEstimate | None:
        return self.repo.get(estimate_id, version)

    def get_references(self, estimate_id: str, version: int | None = None) -> list[Reference]:
        """Reference-class matches for an existing estimate, recomputed fresh
        (not persisted on the graph) so simply opening an estimate shows them,
        not just the moment right after it was created or recalculated."""
        stored = self.repo.get(estimate_id, version)
        if stored is None:
            return []
        graph = stored.graph
        prd_text = "\n".join(f"- {r.text}" for r in graph.requirements)
        past = [s for s in self.repo.all_latest() if s.estimate_id != estimate_id]
        return find_references(prd_text, graph.client_context, graph.matched_pattern_ids, past)

    def update_estimate(self, estimate_id: str, graph: SolutionGraph) -> StoredEstimate:
        """Persist an edited graph as a new version (interactive editing)."""
        return self.repo.update(estimate_id, graph)

    def list_estimates(self):
        return self.repo.list_summaries()

    def record_actuals(self, outcome: ActualOutcome) -> None:
        """Feed delivery actuals into memory for prior calibration (§4.4)."""
        self._actuals[outcome.estimate_id] = outcome

    def compute_scenarios(self, estimate_id: str, scenarios: list[Scenario] | None = None) -> StoredEstimate:
        """Compute staffing/dev-model scenarios, store them, and persist a version."""
        stored = self.repo.get(estimate_id)
        if stored is None:
            raise KeyError(f"estimate {estimate_id!r} not found")
        rows, _ = self.active_rates()
        dev_models, _ = data_loader.load_dev_models()
        specs = scenarios or default_scenarios()
        results = compute_scenarios(stored.graph, specs, RateCard(rows), dev_models)
        graph = stored.graph.model_copy(deep=True)
        graph.scenarios = results
        return self.repo.update(estimate_id, graph)

    def suggest(self, estimate_id: str) -> dict:
        """Advisor: cheaper/faster team models + scope deferrals, grounded in history."""
        stored = self.repo.get(estimate_id)
        if stored is None:
            raise KeyError(f"estimate {estimate_id!r} not found")
        rows, _ = self.active_rates()
        dev_models, _ = data_loader.load_dev_models()
        # History for grounding excludes this estimate itself.
        past = [s for s in self.repo.all_latest() if s.estimate_id != estimate_id]
        team = advisor.suggest_team_models(stored.graph, RateCard(rows), dev_models, past=past)
        deferrals = advisor.suggest_deferrals(stored.graph)
        return {"team": team, "deferrals": deferrals}
