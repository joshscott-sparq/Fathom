# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

Fathom: an agentic estimation and solutioning engine for Sparq's Solutions Consulting
and Delivery teams (an internal tool — not one of Sparq's client-facing ".IQ" AI
offerings, hence the different naming pattern). Named for the nautical unit of depth
and the verb "to fathom" (to grasp the full extent of something), both of which fit a
tool that measures and estimates scope from context. Takes a PRD plus client context
and produces a reference architecture, effort estimate, cost model, and deal-shaping
scenarios. Standalone full-stack app — FastAPI backend (`src/architect_iq/`)
+ React/TypeScript/Tailwind frontend (`frontend/`) — not a library or CLI tool, despite
the `architectiq` console script stub in `pyproject.toml` (not yet implemented; see
DECISIONS.md D11). The Python package/module is still named `architect_iq` on disk —
see below if you're taking on the full code-level rename.

`DECISIONS.md` is the log of every non-obvious judgment call made building this (why
things are the way they are, what was explicitly flagged to the product owner and not
yet resolved). Before working in an area — and especially before "fixing" something
that looks unfinished, inconsistent, or like a bug — grep `DECISIONS.md` for the
module, file, or feature name you're about to touch. It's the difference between
re-litigating a deliberate tradeoff (possibly one still flagged and awaiting owner
input) and actually finding a bug. Add an entry there — not just a code comment — for
future non-obvious calls of your own; D25 is a recent example of the shape (the call,
the why, and what's deliberately left undone).

## Commands

Run both processes with one command from the repo root:

```bash
./dev.sh          # normal app: backend :8000 + frontend :5173
./dev.sh demo     # demo mode: auto-login as admin, sample data
```

It creates `.venv` and installs both sets of dependencies on first run if missing.
Manual equivalent (two terminals, backend first) is in the README Quick start.

Backend tests (from repo root; `pythonpath`/`testpaths` are set in `pyproject.toml`):

```bash
.venv/bin/python -m pytest -q                              # full suite
.venv/bin/python -m pytest tests/test_scenarios.py -q       # one file
.venv/bin/python -m pytest tests/test_scenarios.py::test_default_scenarios_span_models -q  # one test
```

Frontend typecheck/build (from `frontend/`):

```bash
npx tsc -b            # typecheck only
npm run build          # typecheck + vite build
npm run prod            # build + preview on :4173
```

No linter is configured for either side (no ruff/eslint config in the repo).

## Architecture

### The Solution Graph is the one central object

Every artifact (reference architecture, effort estimate, cost model, team plan) is a
projection of a single `SolutionGraph` (`models/solution_graph.py`):
`requirements → capabilities → components → work items → effort → team → cost`, plus
`context_panel`, `complexity_factors`, `scenarios`, `matched_pattern_ids`,
`deterministic`/`monte_carlo`/`reconciliation` results, and `assumptions`. Change one
node and every downstream projection (diagram, cost, timeline) is rebuilt from it —
editing context just rebuilds the graph in place.
(D8: this replaced an earlier flat `EstimateModel`; the legacy calibration workbook is a
reference for defaults, not a contract the math must replicate exactly — D8, D10.)

`SolutionGraph`s are versioned: every edit persists as a new version via
`persistence/store.py` (`SQLiteEstimateRepository`), except the Context Panel's
auto-recalc which overwrites the latest version in place (`overwrite_latest` — D22) so
live editing doesn't spam versions. Deliberate actions (recompute knobs, scenario
compute, re-cost) do snapshot a new version.

### Build pipeline (`service.py` → `core/estimation.py`)

`EstimateService._build_graph()` is the one path that constructs a graph, used by
`create_estimate`, `rebuild_estimate`, and `recalculate_from_context`:

1. `core/matcher.py` scores the PRD + `ClientContext` against the pattern library
   (`data/patterns.yaml`) to pick a reference architecture (RAG-on-Databricks, .NET
   modernization, agentic-on-MCP, …).
2. `memory/priors.py` tunes that pattern's parametric cost from past estimates +
   recorded actuals (`ActualOutcome`) before the graph is built — this is "memory
   improves the next estimate," not a separate offline step.
3. `core/estimation.py::build_estimate()` instantiates the pattern into components/work
   items, derives capabilities (LLM or 1:1 heuristic fallback), decomposes large
   features into stories, applies `core/factors.py` complexity/risk factors (from
   context + the Context Panel's Risks tab — factors from Risks entries carry
   `family="Risk: ..."`) to `core/velocity.py` (sub-linear team scaling, D11 fix), and
   reconciles top-down parametric vs bottom-up rollup into a confidence-weighted blend.
   Monte Carlo (`core/montecarlo.py`, PERT-beta + a correlated systemic-risk factor)
   produces P10/P50/P80/P90 ranges, recentered on the blend.
4. `memory/retrieval.py` finds reference-class estimates to surface in the UI.

`core/recompute.py` (deal-shaping knobs: AI Tier boost, engineer count, allocations) and
`core/scenarios.py` (named staffing/dev-model comparisons) both recompute velocity/cost
against the *same fixed work breakdown* — they never re-match or re-size, only move the
levers. `core/advisor.py` layers cheaper/faster suggestions + deferral candidates on top
of the scenario engine, grounded in reference-class history.

### Data is versioned YAML, not code

`src/architect_iq/data/*.yaml` (patterns, complexity factors, t-shirt scale, variables,
dev models / AI Tiers, pricing) are loaded by `data_loader.py` and cached
(`@lru_cache`). Adding or tuning a pattern, factor, or AI Tier is a data edit, not a code
change — see `dev_models.yaml`'s comment header and D23 for how the 5-tier AI Tier
ladder (human:AI-agent ratio, `ai_boost`/`effort_multiplier` per tier) plugs into
`core/scenarios.py` and `core/advisor.py` purely through that data file's keys.
Real pricing is never committed: `data/pricing.local.yaml` (gitignored) overrides the
committed placeholder `pricing.example.yaml`; `data/SCHEMA.md` documents the format.

### Context Panel drives the estimate, not the other way around

`models/context.py`'s `ContextPanel` (Requirements/Phases/Risks/Accelerators/
Assumptions/External Sources) lives on the `SolutionGraph`. `PUT
/api/estimates/{id}/context` → `service.recalculate_from_context()` rebuilds the PRD
from Requirements entries (falling back to the graph's existing requirements if none),
feeds risks/accelerators/assumptions/phases through `build_estimate()`, and saves in
place — this is the auto-recalc the frontend debounces on every keystroke (D22).

### Semantic kind classification drives Requirements-tab drop routing

`data/estimate_kinds.yaml` → `models/kinds.py::KindTaxonomy` defines 8 kinds a piece of
extracted text can be: work items `epic`/`feature`/`story` (hierarchical — an epic
groups by capability, a story is a single user-facing slice), `story_point` (a measure
attached to a story/feature, never its own node), register items `risk`/`assumption`
(disambiguated by a flip test: a wrong assumption invalidates the estimate, a risk is
something you watch and mitigate), `accelerator` (a modifier that reduces effort/
duration/risk on a work item), and `phase` (a timeline container — orthogonal to epic,
not mutually exclusive; a work item can carry both an epic and a phase reference at
once). Each kind carries a definition, pairwise disambiguation rules against its most
confusable neighbor, and detection signals.

`core/llm.py::classify_kind()` (LLM-primary, feeds the taxonomy's definitions/
disambiguation straight into the prompt, plus a short `title`) and
`heuristic_classify_kind()` (deterministic fallback: word-boundary signal matching,
plus an explicit regex for the "As a ... I want ..." story template) score one
sentence against the taxonomy. A separate batched call, `group_into_epics()` (LLM) /
`heuristic_group_into_epics()` (fallback: one generic epic per batch), clusters
related features/stories under a shared epic name describing what they're about —
never the source filename.

`POST /api/context/decompose-requirements` (called when a file/URL lands on the
Requirements tab) runs both: each returned item carries `taxonomy_kind`,
`taxonomy_confidence`, `title`, and `epic` alongside the existing `duplicate_of`.
The frontend (`ContextPanel.tsx::addExtractedContent`) routes by `taxonomy_kind` —
`risk`/`assumption`/`accelerator` become an entry in that tab (exactly like typing
one by hand); everything else (default `feature`, `story`/`epic` only when the model
says so) becomes a `WorkItem` in the estimate's work breakdown, with `title` as the
grid's short label and the full sentence preserved in `WorkItem.notes` (D26).
Dropping a file now adds exactly **one** Requirements entry (a 2-5 bullet summary),
not a decomposed pile — everything else goes to its real destination instead (D26).

New `WorkItem`-routed items can't be appended to `graph.work_items` via a one-shot
write: `service.recalculate_from_context()` (the Context Panel's debounced
auto-recalc) always rebuilds `work_items` from scratch from the PRD text, so a
separate append would get silently discarded the moment any *other* Context Panel
edit triggers this same recalc again. They're persisted instead in
`ContextPanel.pinned_work_items` — part of the panel, resent on every save — and
`recalculate_from_context` re-appends that field after every rebuild, the same way
a Requirements entry's own text survives repeated recalcs. This durability gap is
still open for D24's hand-editable grid, though: editing a row there, then editing
any Context Panel field, discards the hand-edit the same way `pinned_work_items`
was built to avoid — not solved by D26, since those edits don't have a taxonomy
kind to route through this same mechanism.

### Auth, domain model, persistence

Domain: `Account → Opportunity → Estimate` (one active/official estimate per
opportunity; other versions/clones are non-active). Three roles enforced in
`auth/access.py`: Admin (everything), User (own + shared; memory/training uses *all*
history regardless of ownership), Client (read-only on assigned opportunities). JWT
(HS256) local auth now; Google SSO and JumpCloud drop in via the same OIDC-ready seam
(`auth/oidc.py`). Sharing (view/comment/edit by email or name), public view-only links,
and comments are directory-level concerns in `persistence/directory.py`
(`SQLiteDirectoryRepository`) — separate from `persistence/store.py`'s estimate
versioning and `persistence/rate_cards.py`'s rate-card management (multiple saved cards,
one active + one default).

All three persistence repos share one SQLite file (`ARCHITECTIQ_DB`, default
`architect_iq.db`) — swappable to Postgres behind the same repository interfaces if
needed (README notes this as the multi-instance path).

### Demo mode

Gated by Vite mode, not a runtime toggle: `npm run demo` (`vite --mode demo`) loads
`.env.demo` → `VITE_DEMO_MODE=true` (D12) — this is invisible in `dev`/`prod`, so demo
data/UI never leaks there. `App.tsx`'s bootstrap effect (gated by a `demoTried` ref, not
just component state) auto-logs in as admin and calls `POST /api/demo/seed` once.
`demo.py::seed_demo()` is idempotent by project name across separate calls but **not
concurrency-safe** — two overlapping seed calls (e.g., two tabs open before the first
finishes) can race past each other's idempotency check and double-create scenarios; this
is a known gap, not yet fixed. Seeding calls the real LLM per sample estimate when
`ANTHROPIC_API_KEY` is set (can take ~1-2 min); the frontend shows a "Loading demo
data…" state during that window rather than a misleading empty list.

### Frontend shape

`App.tsx` is the shell: auth gate, role-aware hamburger nav, and the three-zone layout —
header, main output (`EstimateView.tsx`, masonry-column `Section`s that expand to a
full-screen `Modal.tsx`), and the bottom-docked collapsible `ContextPanel.tsx`. `api.ts`
is the single fetch client (bearer token from `localStorage`); `types.ts` mirrors the
backend Pydantic models by hand (no codegen — keep them in sync manually when backend
response shapes change).

## Working with the LLM layer

`core/llm.py` / `core/vision.py` wrap the Anthropic SDK for requirement extraction,
capability derivation, nuanced pattern matching, image/diagram vision, and the advisor's
team-model suggestions. Every one of these has a deterministic heuristic fallback and
runs fully without a key (`ARCHITECTIQ_DISABLE_LLM=1` forces the fallback path even with
a key present) — tests set `use_llm=False` explicitly rather than relying on the key
being absent in the test environment (see `tests/conftest.py`, which also deletes
`ANTHROPIC_API_KEY` from the environment for API-level tests).

## Next steps: development plan toward "fully functional"

Reviewed 2026-07-18 against the actual code (not just DECISIONS.md, which has drifted —
see the first item below). Ordered by what blocks correctness/production use first;
the last two tiers are ongoing maturity work, not one-time fixes.

### 1. Correctness fixes (small, high-value)

- **Prior-tuning can tune the wrong pattern's prior.** `service._build_graph()` picks
  which pattern's prior to tune via `estimation.score_patterns()` — the deterministic
  signal-overlap matcher only. But the graph itself is built by `estimation.build_estimate()`,
  whose internal `_rank_patterns()` uses the real LLM matcher when available and can
  disagree with the deterministic preview. When they disagree, memory tunes the prior
  for a pattern that isn't the one actually used. Fix: have `_build_graph()` build the
  graph first, then tune priors for the pattern it actually matched.
- **`DECISIONS.md` D11 ("known skeleton gaps") is stale.** It lists requirement
  extraction, capability derivation, and LLM pattern matching as not-yet-wired — all
  three are implemented and tested (`core/llm.py`, wired through `core/estimation.py`,
  covered by `tests/test_llm.py`). The engineer-count/cost gap it describes was also
  fixed (see `core/velocity.py`'s "D11 fix" reference). Reconcile or close D11 so it
  doesn't mislead the next person into re-solving solved problems.
- **`seed_demo()` isn't concurrency-safe** — two overlapping `POST /api/demo/seed`
  calls can double-create demo estimates (see CLAUDE.md's Demo mode section above). A
  background task for this was already spawned; confirm it landed before closing.
- **Dangling CLI entry point.** `pyproject.toml`'s `[project.scripts] architectiq =
  "architect_iq.agent.cli:main"` points at a module that doesn't exist — `pip install -e .`
  ships a console script that crashes on invocation. Either remove the entry point until
  a real CLI is built, or build a minimal one (see tier 3).

### 2. Production hardening

- **No CI.** No `.github/workflows` (or equivalent) runs the backend pytest suite or
  frontend typecheck/build on a PR. Add one before this has more than one contributor.
- **No login rate limiting.** `POST /api/auth/login` (`api/app.py`) has no
  attempt-throttling or lockout — brute-forceable as-is. Needed before any non-local
  deployment.
- **Startup only warns, doesn't fail, on insecure defaults.** Missing
  `ARCHITECTIQ_SECRET` / `ARCHITECTIQ_ADMIN_PASSWORD` log a `UserWarning` (see
  `auth/security.py`, `persistence/directory.py`) but the app still starts with the dev
  secret and default admin password. Consider a hard failure when
  `ARCHITECTIQ_ENV=production` (or similar) is set.
- **SQLite → Postgres path is asserted, not built.** README calls this "the
  multi-instance path" behind the same repository interfaces, but no Postgres
  implementation of `EstimateRepository` / `SQLiteDirectoryRepository` /
  `SQLiteRateCardRepository` exists yet. Needed before running more than one backend
  instance.

### 3. Feature completeness (README's "Not yet built", confirmed still true)

- **No xlsx/summary emitters.** `emit/` only has `mermaid.py` (the architecture
  diagram). No SOW-ready doc/spreadsheet export of an estimate exists.
- **Salesforce is ID-linkage only.** `Opportunity.sf_account_id` /
  `sf_opportunity_id` are stored strings with no live Salesforce API client —
  unlike Notion (`integrations/notion.py`), which has a real fetch path behind
  `NOTION_API_KEY`. Decide if live Salesforce sync is in scope; if so, mirror the
  Notion module's key-gated-with-fallback pattern.
- **External Sources data pull is fully stubbed** (D22) beyond Notion — GitHub,
  SpecKit, Slack connections show status but don't pull data yet.
- **Claude skill wrapper** (README) — not started.
- **Team composition re-shaping on recost is limited** (D13): `POST
  /api/estimates/{id}/recost` reprices the existing fixed team under a new rate
  card, but changing tier/location *mix* (not just re-pricing the same roles) is
  still a noted-for-later lever.
- **`pinned_work_items` durability fix (D26) doesn't cover D24's hand-editable grid.**
  Editing a work-item row directly, then editing any Context Panel field, still
  discards the hand-edit — the same rebuild-from-scratch problem D26 solved for
  classifier-routed items, but hand-edits have no taxonomy kind to route through
  that mechanism. Needs its own fix (e.g. a general "manually touched, don't
  regenerate" flag per WorkItem) if this bites in practice.

### 4. Calibration maturity (ongoing — memory loop exists, needs real volume)

- Pattern parametric costs (`data/patterns.yaml`) are starter calibration; they
  self-tune via `memory/priors.py` as real estimates + recorded actuals
  (`ActualOutcome`) accumulate, but there isn't yet enough delivered-engagement
  volume to trust the tuned numbers over the starting defaults.
- AI Tier `ai_boost`/`effort_multiplier` values (D23) are an explicit first-pass
  heuristic pending real per-tier delivery actuals to recalibrate against.
- Several workbook-derived constants (`PesWeight` D3, `AvgStoryPts` D4, complexity
  factor severity curves D5, factor family count D6) are seeded defaults explicitly
  flagged to the product owner and not yet resolved — see each decision entry for
  what's needed to close it.

### 5. Testing gaps

- **No frontend test automation.** `frontend/` has `tsc -b` (typecheck) and manual
  browser verification only — no component tests (Vitest/RTL) or E2E (Playwright).
  Backend has solid pytest coverage; frontend logic (Context Panel auto-recalc
  debounce, AI Tier picker, scenario tables) is currently only regression-tested by
  hand.
