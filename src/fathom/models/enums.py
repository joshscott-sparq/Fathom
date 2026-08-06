"""Shared enumerations. Values mirror the workbook vocabulary (spec §2)."""

from __future__ import annotations

from enum import Enum


class WorkLevel(str, Enum):
    """Hierarchy level of a work item (§2.1 blank-cell convention)."""

    EPIC = "epic"
    FEATURE = "feature"
    STORY = "story"


class TShirtSize(str, Enum):
    """T-shirt sizes from ResourceLookups!A62:D71 (§2.2)."""

    XXXS = "XXXS"
    XXS = "XXS"
    XS = "XS"
    S = "S"
    M = "M"
    L = "L"
    XL = "XL"
    XXL = "XXL"
    XXXL = "XXXL"


class RiskSeverity(str, Enum):
    """Risk severity ladder (§2.4). Impacts resolved from variables.yaml."""

    NONE = "None"
    LOW = "Low"
    MODERATE = "Moderate"
    HIGH = "High"
    EXTREME = "Extreme"


class FactorScope(str, Enum):
    """Scope at which a linked complexity/risk factor applies.

    PROJECT and PHASE scopes feed ComplexityImpact in the velocity model (§2.3).
    ITEM scope (no project/phase scope) adds directly to the work item (§2.1),
    multiplied at epic/feature level.
    """

    PROJECT = "project"
    PHASE = "phase"
    ITEM = "item"


class Location(str, Enum):
    """Pricing location (§2.6). US = onshore, NS = nearshore."""

    US = "US"
    NS = "NS"
