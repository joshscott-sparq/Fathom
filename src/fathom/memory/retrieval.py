"""Reference-class retrieval (spec §4.4).

Given a new PRD + client context, surface similar past estimates so the estimate
starts from a reference class instead of a cold start ("learn up front"). This is
the read side of memory; `priors.py` is the calibration side.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from ..models.results import ClientContext
from ..persistence.store import StoredEstimate

_WORD = re.compile(r"[a-z0-9]+")


def _tokens(text: str) -> set[str]:
    return set(_WORD.findall(text.lower()))


def _jaccard(a: set[str], b: set[str]) -> float:
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


@dataclass
class Reference:
    estimate_id: str
    project_name: str
    similarity: float
    why: str
    cost_p50: float | None
    effort_p50: float | None


def find_references(
    prd_text: str,
    context: ClientContext,
    matched_pattern_ids: list[str],
    past: list[StoredEstimate],
    limit: int = 5,
) -> list[Reference]:
    """Rank past estimates by similarity to the new inputs.

    Similarity blends: shared matched pattern (0.6), client tech-stack overlap
    (0.3, Jaccard), and PRD/project token overlap (0.1). Pattern match dominates
    because same-pattern engagements are the strongest reference class (§4.2).
    """
    matched = set(matched_pattern_ids)
    query_tech = {t.lower() for t in context.tech_stack}
    query_tokens = _tokens(prd_text)

    references: list[Reference] = []
    for stored in past:
        g = stored.graph
        reasons: list[str] = []

        pattern_overlap = bool(matched & set(g.matched_pattern_ids))
        pattern_score = 0.6 if pattern_overlap else 0.0
        if pattern_overlap:
            reasons.append(f"same pattern ({', '.join(matched & set(g.matched_pattern_ids))})")

        past_tech = {t.lower() for t in g.client_context.tech_stack}
        tech_score = 0.3 * _jaccard(query_tech, past_tech)
        if query_tech & past_tech:
            reasons.append(f"shared tech: {', '.join(sorted(query_tech & past_tech))}")

        token_score = 0.1 * _jaccard(query_tokens, _tokens(g.project_name))

        similarity = round(pattern_score + tech_score + token_score, 4)
        if similarity <= 0:
            continue
        references.append(
            Reference(
                estimate_id=stored.estimate_id,
                project_name=g.project_name,
                similarity=similarity,
                why="; ".join(reasons) or "weak token overlap",
                cost_p50=g.monte_carlo.cost.p50 if g.monte_carlo else None,
                effort_p50=g.monte_carlo.effort_points.p50 if g.monte_carlo else None,
            )
        )

    references.sort(key=lambda r: r.similarity, reverse=True)
    return references[:limit]
