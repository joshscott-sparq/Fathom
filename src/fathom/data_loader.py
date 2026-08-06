"""Load the versioned YAML lookup tables into typed structures (spec §2, build step 1).

Every table is loaded here so the rest of the engine never reads raw YAML. Pricing
resolves `pricing.local.yaml` (real rates, gitignored) before falling back to
`pricing.example.yaml` (placeholder rates). See data/SCHEMA.md.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

import yaml

from .models.complexity import ComplexityFactor
from .models.enums import Location, RiskSeverity
from .models.kinds import KindDefinition, KindDisambiguation, KindTaxonomy
from .models.pattern import ComponentSpec, IntegrationSpec, ParametricCost, Pattern
from .models.practice import DisciplineConstraint, Practice, PracticeLibrary
from .models.team import RateRow, Tier
from .models.variables import Variables

DATA_DIR = Path(__file__).parent / "data"

# Maps variables.yaml keys to Variables field names.
_VARIABLE_FIELD_MAP = {
    "RealWeight": "real_weight",
    "OptWeight": "opt_weight",
    "PesWeight": "pes_weight",
    "EpicMultiplier": "epic_multiplier",
    "FeatureMultiplier": "feature_multiplier",
    "AvgStoryPts": "avg_story_pts",
    "AIBoostMin": "ai_boost_min",
    "AIBoostMax": "ai_boost_max",
    "BARatio": "ba_ratio",
    "DesignerRatio": "designer_ratio",
    "DevOpsRatio": "devops_ratio",
    "QARatio": "qa_ratio",
    "HoursPerSprint": "hours_per_sprint",
    "WeeksInSprint": "weeks_in_sprint",
    "WorkingMonthDays": "working_month_days",
    "HoursPerDay": "hours_per_day",
    "RiskImpactLow": "risk_impact_low",
    "RiskImpactModerate": "risk_impact_moderate",
    "RiskImpactHigh": "risk_impact_high",
    "RiskImpactExtreme": "risk_impact_extreme",
}


def _read_yaml(name: str) -> dict:
    path = DATA_DIR / name
    with path.open("r", encoding="utf-8") as fh:
        return yaml.safe_load(fh)


@lru_cache(maxsize=1)
def load_tshirt_scale() -> tuple[dict[str, dict[str, float]], str]:
    """Return (sizes, version). sizes[size][level] -> points (§2.2)."""
    raw = _read_yaml("tshirt_scale.yaml")
    return raw["sizes"], raw["version"]


@lru_cache(maxsize=1)
def load_variables() -> tuple[Variables, str]:
    """Return (Variables with workbook defaults, version) (§2.1, 2.3, 2.5)."""
    raw = _read_yaml("variables.yaml")
    kwargs = {}
    for key, entry in raw["variables"].items():
        field = _VARIABLE_FIELD_MAP.get(key)
        if field is not None:
            kwargs[field] = entry["value"]
    return Variables(**kwargs), raw["version"]


@lru_cache(maxsize=1)
def load_complexity_factors() -> tuple[dict[str, ComplexityFactor], str]:
    """Return (family_name -> ComplexityFactor, version) (§2.4).

    Resolves each family's level impacts from the severity ladder, with `baseline`
    overriding the first level (for families that start at -0.25).
    """
    raw = _read_yaml("complexity_factors.yaml")
    ladder = {RiskSeverity(k): float(v) for k, v in raw["severity_ladder"].items()}
    provenance = raw.get("provenance_default", "")

    factors: dict[str, ComplexityFactor] = {}
    for entry in raw["families"]:
        levels = [RiskSeverity(level) for level in entry["levels"]]
        impacts: dict[RiskSeverity, float] = {}
        for index, level in enumerate(levels):
            # First available level takes the family baseline; the rest follow the ladder.
            impacts[level] = float(entry["baseline"]) if index == 0 else ladder[level]
        factor = ComplexityFactor(
            family=entry["family"],
            category=entry["category"],
            baseline=float(entry["baseline"]),
            levels=levels,
            level_impacts=impacts,
            provenance=provenance,
        )
        factors[factor.family] = factor
    return factors, raw["version"]


@lru_cache(maxsize=1)
def load_practices() -> tuple[PracticeLibrary, str]:
    """Return (PracticeLibrary, version) (§2.7)."""
    raw = _read_yaml("practices.yaml")
    practices = [
        Practice(name=name, disciplines=body["disciplines"])
        for name, body in raw["practices"].items()
    ]
    constraints = [
        DisciplineConstraint(
            discipline=discipline,
            min_tier=body.get("min_tier"),
            note=body.get("note", ""),
        )
        for discipline, body in raw.get("discipline_constraints", {}).items()
    ]
    return PracticeLibrary(practices=practices, constraints=constraints), raw["version"]


@lru_cache(maxsize=1)
def load_estimate_kinds() -> tuple[KindTaxonomy, str]:
    """Return (KindTaxonomy, version) — the semantic kind taxonomy used to
    classify a piece of extracted text (core/llm.py::classify_kind)."""
    raw = _read_yaml("estimate_kinds.yaml")
    kinds = [
        KindDefinition(
            name=k["name"],
            role=k["role"],
            definition=k["definition"],
            parent=k.get("parent"),
            children=k.get("children", []),
            carries=k.get("carries", []),
            attribute_of=k.get("attribute_of", []),
            modifies=k.get("modifies", []),
            disambiguation=[KindDisambiguation(**d) for d in k.get("disambiguation", [])],
            signals=k.get("signals", []),
            placement=k.get("placement", ""),
        )
        for k in raw["kinds"]
    ]
    return KindTaxonomy(kinds=kinds), raw["version"]


@lru_cache(maxsize=1)
def load_tiers() -> tuple[list[Tier], list[str], list[str], str]:
    """Return (tiers, locations, priority_disciplines, version) (§2.6)."""
    raw = _read_yaml("tiers.yaml")
    tiers = [Tier(name=t["name"], weight=t["weight"]) for t in raw["tiers"]]
    return tiers, raw["locations"], raw.get("priority_disciplines", []), raw["version"]


@lru_cache(maxsize=1)
def load_pricing() -> tuple[list[RateRow], str, str]:
    """Return (rate rows, version, source_file).

    Prefers pricing.local.yaml (real rates, gitignored); falls back to
    pricing.example.yaml (placeholder rates). See data/SCHEMA.md.
    """
    local = DATA_DIR / "pricing.local.yaml"
    source_file = "pricing.local.yaml" if local.exists() else "pricing.example.yaml"
    raw = _read_yaml(source_file)
    rows = [
        RateRow(
            discipline=r["discipline"],
            tier=r["tier"],
            location=Location(r["location"]),
            day_rate=r["day_rate"],
        )
        for r in raw["rates"]
    ]
    return rows, raw["version"], source_file


@lru_cache(maxsize=1)
def load_dev_models() -> tuple[dict[str, dict], str]:
    """Return (tier_key -> {name, tier, human_ratio, ai_ratio, human_role, ai_role,
    ai_boost, effort_multiplier, assumptions}, version) — the AI Tier ladder."""
    raw = _read_yaml("dev_models.yaml")
    return raw["models"], raw["version"]


@lru_cache(maxsize=1)
def load_patterns() -> tuple[dict[str, Pattern], str]:
    """Return (pattern_id -> Pattern, version) from the pattern library (§4.2)."""
    raw = _read_yaml("patterns.yaml")
    patterns: dict[str, Pattern] = {}
    for entry in raw["patterns"]:
        cost = entry["parametric_cost"]
        pattern = Pattern(
            id=entry["id"],
            name=entry["name"],
            description=entry.get("description", ""),
            when_to_use=entry.get("when_to_use", ""),
            match_signals=entry.get("match_signals", []),
            components=[ComponentSpec(**c) for c in entry.get("components", [])],
            integrations=[IntegrationSpec(**i) for i in entry.get("integrations", [])],
            parametric_cost=ParametricCost(
                base_effort_points=cost["base_effort_points"],
                scaling_drivers=cost.get("scaling_drivers", {}),
                risk_factor_families=cost.get("risk_factor_families", []),
            ),
        )
        patterns[pattern.id] = pattern
    return patterns, raw["version"]
