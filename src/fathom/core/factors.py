"""Derive and apply complexity/risk factors (spec §2.3, §2.4).

Turns the estimate's inputs (integrations, compliance posture, tech familiarity,
legacy signals, and the matched pattern's risk families) into LinkedFactors with
velocity impacts from the complexity-factor library, then sums them into a
ComplexityImpact that reduces velocity. Previously this library was inert data;
now it moves the number, so the estimate responds to risk and context.
"""

from __future__ import annotations

from .. import data_loader
from ..models.complexity import LinkedFactor
from ..models.enums import FactorScope, RiskSeverity
from ..models.graph import Component, Edge, EdgeKind
from ..models.pattern import Pattern
from ..models.results import ClientContext

# High-scrutiny compliance regimes push Sec & Compliance severity up.
_HIGH_COMPLIANCE = {"hipaa", "pci", "pci dss", "fedramp", "hitrust", "gdpr", "sox"}
# Fraction of AvgStoryPts velocity can be eroded by complexity (floor guard).
_MAX_EROSION = 0.7


def _severity_for_count(n: int, low: int, moderate: int) -> RiskSeverity:
    if n <= low:
        return RiskSeverity.LOW
    if n <= moderate:
        return RiskSeverity.MODERATE
    return RiskSeverity.HIGH


def derive_factors(
    components: list[Component],
    edges: list[Edge],
    context: ClientContext,
    pattern: Pattern,
    prd_text: str,
) -> list[LinkedFactor]:
    """Infer the complexity/risk factors this engagement carries."""
    library, _ = data_loader.load_complexity_factors()
    chosen: dict[str, RiskSeverity] = {}

    def consider(family: str, severity: RiskSeverity) -> None:
        cf = library.get(family)
        if cf is None:
            return
        sev = severity if severity in cf.level_impacts else cf.levels[-1]
        # Keep the highest severity if a family is implied by multiple signals.
        if family not in chosen or cf.level_impacts[sev] < cf.level_impacts[chosen[family]]:
            chosen[family] = sev

    # Integrations: more edges -> higher severity (family starts at -0.25).
    n_integrations = sum(1 for e in edges if e.kind in {EdgeKind.INTEGRATES_WITH, EdgeKind.DATA_FLOW})
    if n_integrations:
        consider("Integrations", _severity_for_count(n_integrations, 2, 4))

    # Security & compliance from the client's posture (§3.4).
    posture = [p.lower() for p in context.compliance_posture]
    if posture:
        high = any(any(h in p for h in _HIGH_COMPLIANCE) for p in posture)
        consider("Sec & Compliance Risks", RiskSeverity.HIGH if high else RiskSeverity.MODERATE)

    # Tech familiarity: does the client team's skillset cover the tech stack?
    stack = {t.lower() for t in context.tech_stack}
    skills = {s.lower() for s in context.team_skills}
    if stack:
        covered = sum(1 for t in stack if any(t in s or s in t for s in skills))
        ratio = covered / len(stack)
        if ratio < 0.34:
            consider("Familiarity w/ Tech", RiskSeverity.MODERATE)
        elif ratio < 0.67:
            consider("Familiarity w/ Tech", RiskSeverity.LOW)

    # Legacy ecosystem from the pattern or PRD language.
    prd_lower = prd_text.lower()
    if pattern.id == "dotnet-modernization" or any(w in prd_lower for w in ("legacy", "monolith", "mainframe")):
        consider("Legacy Ecosystem", RiskSeverity.MODERATE)

    # The pattern's known risk families (testing complexity, data quality, etc.)
    # seed at a low baseline unless already implied more strongly above.
    for family in pattern.parametric_cost.risk_factor_families:
        consider(family, RiskSeverity.LOW)

    factors: list[LinkedFactor] = []
    for family, severity in chosen.items():
        cf = library[family]
        factors.append(
            LinkedFactor(
                family=family, severity=severity, scope=FactorScope.PROJECT,
                impact=cf.impact_for(severity), is_risk=True,
            )
        )
    return factors


def complexity_impact(factors: list[LinkedFactor], avg_story_pts: float) -> float:
    """Sum factor impacts into a velocity delta, floored so velocity stays positive."""
    total = sum(f.net_impact for f in factors)
    return max(total, -_MAX_EROSION * avg_story_pts)


def risk_sigma(factors: list[LinkedFactor], divergence_pct: float = 0.0) -> float:
    """Systemic (correlated) Monte Carlo sigma from aggregate risk + reconciliation
    divergence. More and more-severe factors, and a bigger top-down vs bottom-up
    gap, widen the distribution."""
    base = 0.10
    from_factors = 0.03 * len(factors) + 0.04 * sum(1 for f in factors if f.impact <= -0.5)
    from_divergence = 0.5 * min(abs(divergence_pct), 0.5)
    return round(min(base + from_factors + from_divergence, 0.40), 4)
