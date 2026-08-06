"""Architect.IQ: agentic estimation and solutioning engine (Phase 1).

See architect-iq-context.md for the authoritative spec.
"""

# Load .env (ANTHROPIC_API_KEY, FATHOM_* settings) as early as possible so
# the LLM layer and the Anthropic SDK see it. No-op if python-dotenv is absent.
try:  # pragma: no cover - environment convenience
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:
    pass

__version__ = "0.1.0"
