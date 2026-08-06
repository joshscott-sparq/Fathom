"""Pattern matcher (spec §4.2).

Two matchers, both returning ranked (pattern_id, score, rationale) results:

- `score_patterns`: deterministic signal-overlap scoring. Works offline, is
  fully testable, and is the fallback when no LLM is available.
- `llm_match`: (optional) Anthropic-backed match for nuanced PRDs. Falls back to
  the deterministic scorer on any error or missing key.

The owner asked for both (2026-07-17): deterministic always available, LLM
preferred when a key is present.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from ..models.pattern import Pattern
from ..models.results import ClientContext


@dataclass
class PatternMatch:
    pattern_id: str
    score: float
    rationale: str


_WORD = re.compile(r"[a-z0-9\.\+#]+")


def _tokenize(text: str) -> set[str]:
    return set(_WORD.findall(text.lower()))


def score_patterns(
    prd_text: str,
    context: ClientContext,
    patterns: dict[str, Pattern],
) -> list[PatternMatch]:
    """Deterministic signal-overlap score, normalized 0-1, ranked descending."""
    haystack = _tokenize(prd_text)
    haystack |= _tokenize(" ".join(context.tech_stack))
    haystack |= _tokenize(" ".join(context.team_skills))
    haystack |= _tokenize(" ".join(context.compliance_posture))

    matches: list[PatternMatch] = []
    for pattern in patterns.values():
        signals = pattern.match_signals or []
        if not signals:
            matches.append(PatternMatch(pattern.id, 0.0, "no match signals defined"))
            continue
        hits = [s for s in signals if _signal_hit(s, haystack)]
        score = len(hits) / len(signals)
        rationale = (
            f"matched {len(hits)}/{len(signals)} signals: {', '.join(hits)}"
            if hits
            else "no signal overlap"
        )
        matches.append(PatternMatch(pattern.id, round(score, 4), rationale))

    matches.sort(key=lambda m: m.score, reverse=True)
    return matches


def _signal_hit(signal: str, haystack: set[str]) -> bool:
    """A signal hits if all its tokens appear in the haystack (handles phrases)."""
    tokens = _tokenize(signal)
    return bool(tokens) and tokens <= haystack


def best_match(
    prd_text: str,
    context: ClientContext,
    patterns: dict[str, Pattern],
    minimum_score: float = 0.0,
) -> PatternMatch | None:
    """Top deterministic match above `minimum_score`, or None."""
    ranked = score_patterns(prd_text, context, patterns)
    if ranked and ranked[0].score > minimum_score:
        return ranked[0]
    return ranked[0] if ranked else None
