"""Step 1 contract: data files load and models validate (spec §2)."""

import math

import pytest

from fathom.data_loader import (
    load_complexity_factors,
    load_estimate_kinds,
    load_practices,
    load_pricing,
    load_tiers,
    load_tshirt_scale,
    load_variables,
)
from fathom.models import (
    CureAssessment,
    RiskSeverity,
    ThreePoint,
    TShirtSize,
    WorkItem,
    WorkLevel,
)


def test_tshirt_scale_matches_spec_2_2():
    sizes, version = load_tshirt_scale()
    assert version == "1.0.0"
    # Exact values from ResourceLookups!A62:D71 (§2.2).
    assert sizes["M"] == {"epic": 50, "feature": 12.5, "story": 5}
    assert sizes["XXXS"]["story"] == 0.5
    assert sizes["XXXL"]["epic"] == 340
    assert set(sizes) == {"XXXS", "XXS", "XS", "S", "M", "L", "XL", "XXL", "XXXL"}


def test_tshirt_multiplier_relationships():
    """§2.2 table is story-point-scaled: feature = 2.5 stories, epic = 10 stories."""
    sizes, _ = load_tshirt_scale()
    for size, cols in sizes.items():
        assert math.isclose(cols["feature"], cols["story"] * 2.5), size
        assert math.isclose(cols["epic"], cols["story"] * 10), size


def test_variables_defaults():
    variables, version = load_variables()
    assert version == "1.0.0"
    # PERT weights (§2.1).
    assert variables.real_weight == 1.0
    assert variables.opt_weight == 0.95
    assert variables.pes_weight == 1.2
    # Velocity + ratios (§2.3, §2.5).
    assert variables.avg_story_pts == 9.0
    assert variables.ba_ratio == 0.1
    assert variables.designer_ratio == 0.2
    assert variables.devops_ratio == 0.4
    assert variables.qa_ratio == 0.4
    assert variables.hours_per_sprint == 80.0
    assert variables.working_month_days == 21


def test_complexity_factors_load():
    factors, version = load_complexity_factors()
    assert version == "1.0.0"
    # Named families the agentic loop references directly (§3.4).
    assert "Sec & Compliance Risks" in factors
    assert "Familiarity w/ Tech" in factors
    assert "Integrations" in factors


def test_exception_families_start_at_minus_025():
    """§2.4: integrations, security/compliance, staffing difficulty start at -0.25."""
    factors, _ = load_complexity_factors()
    for name in ("Integrations", "Sec & Compliance Risks", "Staffing Difficulty"):
        factor = factors[name]
        first_level = factor.levels[0]
        assert factor.impact_for(first_level) == -0.25, name


def test_standard_family_starts_at_zero():
    factors, _ = load_complexity_factors()
    team_size = factors["Team Size"]
    assert team_size.impact_for(team_size.levels[0]) == 0.0
    # Ladder holds for deeper levels.
    assert team_size.impact_for(RiskSeverity.MODERATE) == -0.5


def test_practices_map_disciplines():
    library, version = load_practices()
    assert version == "1.0.0"
    assert library.practice_of("Data Engineering") == "Data, Analytics & AI"
    assert library.practice_of("Cloud") == "Platform Engineering & Cloud"
    # Solutions Architect tier constraint (§2.7).
    constraint = next(c for c in library.constraints if c.discipline == "Solutions Architect")
    assert constraint.min_tier == "Senior Lead"


def test_tiers_ordered_weights():
    tiers, locations, priority, version = load_tiers()
    assert version == "1.0.0"
    weights = [t.weight for t in tiers]
    assert weights == sorted(weights)  # ascending Associate..Director
    assert tiers[0].name == "Associate"
    assert tiers[-1].name == "Director"
    assert locations == ["US", "NS"]
    assert "Project & Program Management" in priority


def test_pricing_falls_back_to_example():
    rows, version, source_file = load_pricing()
    assert source_file == "pricing.example.yaml"  # no local file committed
    assert version  # semver string present
    assert all(r.day_rate >= 0 for r in rows)


def test_estimate_kinds_taxonomy_loads():
    taxonomy, version = load_estimate_kinds()
    assert version == "1.0.0"
    assert taxonomy.names() == [
        "epic", "feature", "story", "story_point", "risk", "assumption", "accelerator", "phase",
    ]
    epic = taxonomy.get("epic")
    assert epic.role == "work_item"
    assert epic.children == ["feature"]
    assert any(d.against == "phase" for d in epic.disambiguation)
    risk = taxonomy.get("risk")
    assert "dependency on" in risk.signals


def test_work_item_hierarchy_validation():
    cure = CureAssessment(complexity=3, unknowns=2, risks=2, effort=3, rationale="x", confidence=0.8)
    points = ThreePoint(realistic=5)

    # Valid epic-level row: blank feature and story.
    epic = WorkItem(id="e1", level=WorkLevel.EPIC, epic="Checkout", points=points, cure=cure, extraction_confidence=0.9)
    assert epic.feature is None

    # Feature-level requires a feature, forbids a story.
    with pytest.raises(ValueError):
        WorkItem(id="f1", level=WorkLevel.FEATURE, epic="Checkout", points=points, cure=cure, extraction_confidence=0.9)

    # Story-level requires both.
    story = WorkItem(
        id="s1", level=WorkLevel.STORY, epic="Checkout", feature="Cart", story="Add item",
        tshirt=TShirtSize.M, points=points, cure=cure, extraction_confidence=0.9,
    )
    assert story.story == "Add item"


def test_three_point_blank_substitution():
    """§2.1: blank optimistic/pessimistic substitute the realistic value."""
    tp = ThreePoint(realistic=8)
    assert tp.effective_optimistic == 8
    assert tp.effective_pessimistic == 8

    tp2 = ThreePoint(realistic=8, optimistic=5, pessimistic=13)
    assert tp2.effective_optimistic == 5
    assert tp2.effective_pessimistic == 13

    # Ordering enforced.
    with pytest.raises(ValueError):
        ThreePoint(realistic=8, optimistic=10)
