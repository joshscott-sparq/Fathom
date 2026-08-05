# Fathom

Fathom is named for the nautical unit of depth and the verb "to fathom" — to
grasp the full extent of something — fitting for an agentic estimation and
solutioning engine built for Sparq's Solutions Consulting and Delivery teams (an
internal instrument, not one of Sparq's client-facing ".IQ" AI offerings). It
takes a PRD plus client context (tech stack, compliance posture, team skills) and
produces a reference architecture, effort estimate, cost model, and deal-shaping
scenarios, compressing the discovery-to-SOW cycle.

Built architecture-first around a **Solution Graph**
(`requirements → capabilities → components → work items → effort → team → cost`):
every artifact is a projection of one object. See
[`DECISIONS.md`](DECISIONS.md) for judgment calls.

## Features

**Estimation**
- **Live editor**: the estimate builds from whatever you've entered and
  updates as you add requirements/context, auto-saving in place. Deliberate
  actions (recompute, scenarios, re-cost) snapshot versions.
- **Clone** an estimate to test alternative assumptions (a clone is never the
  opportunity's active/official estimate).
- Architecture-first: PRD + client context matched to a reference pattern
  (RAG on Databricks, .NET modernization, agentic-on-MCP), instantiated into
  components, work items, effort, team, and cost.
- **Risk-aware velocity**: complexity/risk factors (integrations, compliance,
  tech familiarity, legacy, pattern risk families) are derived from context and
  reduce velocity — so the estimate responds to risk, not just scope.
- **Correlated Monte Carlo** (PERT-beta + a systemic risk factor) giving
  defensible P10/P50/P80/P90 ranges for effort, duration, and cost; confidence
  and top-down/bottom-up divergence widen the range.
- **Blended reconciliation**: a confidence-weighted blend of the top-down
  parametric and bottom-up rollup is the working number; large features decompose
  into stories for a finer rollup.
- Sub-linear team velocity (diminishing returns) so more engineers shorten the
  timeline without looking artificially cheaper.
- **Work breakdown grid**: the generated Epic/Feature/Story rows (R/O/P points,
  Phase, Practice) are directly hand-editable and auto-save — add/remove rows,
  size at whichever level fits, link a row to a Phase, and pick a Practice
  from the active rate card rather than free text.

**Context Panel** (bottom-docked, collapsible)
- Seven tabs — Requirements, Phases, Risks, Accelerators, Assumptions,
  Reference Estimates, External Sources — each an editable grid of entries
  added by manual text, dropped file, or URL. Complexity factors derived from
  context show as a read-only block alongside Risks.
- Risks/Accelerators/Assumptions carry a scope (entire estimate or a phase);
  risks reduce velocity, accelerators offset it, assumptions are recorded.
- Reference Estimates surfaces similar past estimates from memory, recomputed
  every time the estimate is opened (not just at creation).
- External Sources (SparqOS default read-only, plus SpecKit/GitHub/Salesforce/
  Notion/Slack/Other) — configurable connections with status; data pull stubbed
  pending credentials.
- Editing context auto-recalculates the estimate above, whose own Estimate /
  Shape It / Outputs tabs separate the number itself from the levers that
  shape it and the artifacts it produces.

**Context ingestion**
- Drag-and-drop or paste: `.md/.txt`, `.docx`, `.pdf`, `.xlsx`, `.csv`, and images.
- With an API key, Claude extracts requirements, derives capabilities, matches
  patterns, and reads architecture diagrams / requirement images (vision).
  Without a key, deterministic heuristics run the whole pipeline.
- Dropped documents are checked against what's already captured — a
  near-duplicate requirement is grouped with its match and flagged rather
  than silently added or dropped.

**Semantic layer**
- A taxonomy-driven classifier (`data/estimate_kinds.yaml`) distinguishes what
  a piece of extracted text *is* — epic, feature, story, story point, risk,
  assumption, accelerator, or phase — each with a definition and a pairwise
  disambiguation rule against its most confusable neighbor (risk vs.
  assumption, epic vs. phase, feature vs. accelerator). Same
  LLM-with-deterministic-fallback pattern as the rest of ingestion. Built as a
  standalone model; not yet wired to auto-route context (see
  [`DECISIONS.md`](DECISIONS.md) D25).

**Scenarios & advisor**
- **AI Tiers**: a 5-tier human-to-AI-agent ratio ladder (Tier 1 fully manual through
  Tier 5's 1:20 human-to-agent ratio), each with a defined human role, AI role, and
  velocity/effort impact — data-driven in [`dev_models.yaml`](src/architect_iq/data/dev_models.yaml).
- Multiple staffing models per estimate — every AI Tier; US / nearshore / blended —
  computed and compared side by side. The active estimate's Deal-shaping panel
  picks a Tier directly (replaces a free-form AI-boost slider).
- Optimization advisor suggests cheaper/faster team models (with real numbers)
  and features to defer to a later release, grounded in historical estimates.

**UI**
- Light/dark mode, collapsible sections, Google-Drive-style **Share** at the
  top of an estimate, comments, and editable **tags**.

**Rate cards & deal-shaping**
- Multiple saved rate cards (one active, one default); upload `.csv/.xlsx/.yaml`.
  A digested Sparq rate card is in [`examples/`](examples/) (`sparq-current-rates.csv`
  is loadable; `.md` is the readable hourly table).
- Interactive sliders (AI boost, team size) recompute live; re-cost under any card.
- Client-safe orals mode hides pricing.

**Memory (gets better over time)**
- Versioned Solution Graphs persist every estimate and edit.
- Reference-class retrieval surfaces similar past estimates; pattern priors
  self-tune from past estimates and recorded delivery actuals.

**Accounts, opportunities & access**
- Domain model: Account → Opportunity → Estimate. An opportunity has many
  estimates but one active/official one. Salesforce account/opportunity IDs and a
  Notion page ref are linked per opportunity; Notion notes surface in-app.
- **Roles:** Admin (manage everything + users/accounts/opportunities/rates),
  User (owns estimates; sees own + shared; memory/training still uses all
  history), Client (read-only on assigned opportunities).
- **Sharing:** share an estimate by email or by a known user's name at
  view / comment / edit; generate public **view-only links** that work without
  login; comment threads on estimates.
- **Auth:** local email+password now, JWT sessions; Google SSO drops in via env
  config, JumpCloud via the same OIDC path.

**Demo mode** — `./dev.sh demo` (or `npm run demo` in `frontend/`) auto-logs in
as admin and loads curated sample data covering every feature: three roles,
accounts/opportunities, three distinct architectures, memory/prior tuning,
versioning, scenarios, sharing, comments, tags, and a fully-populated
**Context Panel** exercising every tab. Seeds automatically on a fresh
database.

## Sample logins (dev)

Seeded on first run for now (set `FATHOM_ADMIN_PASSWORD` and rotate in
production):

| Role | Email | Password |
|------|-------|----------|
| Admin | `admin@teamsparq.com` | `admin123` |
| User | `user@teamsparq.com` | `user123` |
| Client | `client@teamsparq.com` | `client123` |

The sample client is assigned to the Acme Insurance account in demo mode, so they
see those estimates read-only.

## Architecture

| Layer | Location | What it does |
|-------|----------|--------------|
| Core engine | `src/architect_iq/core/` | matcher, estimation, Monte Carlo, recompute, scenarios, advisor, rates, velocity, vision, llm |
| Models | `src/architect_iq/models/` | Solution Graph, work items, patterns, scenarios |
| Data (versioned) | `src/architect_iq/data/` | t-shirt scale, variables, complexity factors, patterns, dev models, pricing, estimate-kind taxonomy |
| Persistence | `src/architect_iq/persistence/` | SQLite: versioned graphs + rate cards |
| Memory | `src/architect_iq/memory/` | reference-class retrieval + pattern-prior tuning |
| API | `src/architect_iq/api/` | FastAPI |
| Frontend | `frontend/` | React + TypeScript + Tailwind (Vite) |

## Configuration

Copy [`.env.example`](.env.example) to `.env` (gitignored) and set values:

| Variable | Purpose |
|----------|---------|
| `ANTHROPIC_API_KEY` | Enables LLM ingest/matching/advisor and image vision. Omitted → deterministic fallback. |
| `FATHOM_LLM_MODEL` | Override the Claude model (default `claude-sonnet-5`). |
| `FATHOM_DISABLE_LLM` | Force the deterministic path even with a key. |
| `FATHOM_DB` | SQLite path (default `architect_iq.db`). |
| `FATHOM_CORS` | Allowed API origins (comma-separated). |
| `FATHOM_SECRET` | **Required in production** — JWT signing secret (32+ bytes). |
| `FATHOM_ADMIN_EMAIL` / `FATHOM_ADMIN_PASSWORD` | Override the seeded admin credentials. |
| `GOOGLE_CLIENT_ID` / `GOOGLE_CLIENT_SECRET` / `GOOGLE_REDIRECT_URI` | Enable Google SSO. |
| `NOTION_API_KEY` | Enable live Notion notes (otherwise sample notes). |

Real pricing is never committed: `data/pricing.local.yaml` (gitignored) overrides
the committed placeholder `pricing.example.yaml`. You can also manage rate cards
at runtime in the **Rates** tab. Schema: [`data/SCHEMA.md`](src/architect_iq/data/SCHEMA.md).

## Quick start

The app is two processes — a FastAPI backend and a Vite frontend. `./dev.sh`
starts both with one command (installs dependencies on first run if missing):

```bash
./dev.sh          # normal app
./dev.sh demo     # demo mode: auto-logs in as admin with sample data (easiest first run)
```

Open the URL Vite prints (default http://localhost:5173). Ctrl+C stops both.

**First demo run seeds sample data by calling the backend** — near-instant with
no `ANTHROPIC_API_KEY` set, or up to ~1-2 minutes if it's set (each of the 5
sample estimates calls the real LLM). Give it time rather than reloading or
opening a second tab mid-seed, which can race and create duplicate estimates.

If Vite reports port 5173 in use, it serves on the next port (5174, …); open
the URL it actually prints rather than assuming 5173.

<details>
<summary>Running the two processes manually (equivalent to <code>dev.sh</code>)</summary>

Terminal 1 (backend, port 8000):

```bash
uv venv --python 3.12
uv pip install -e ".[dev]"
.venv/bin/python -m uvicorn architect_iq.api.app:app --port 8000 --reload
```

Terminal 2 (frontend, proxies `/api` → `:8000`), started **after** the backend is up:

```bash
cd frontend
npm install
npm run demo     # demo mode
# npm run dev    # normal app (log in with a sample account below)
```

Demo mode needs the backend running first — if it isn't, the sign-in screen
shows "Couldn't reach the backend on :8000."
</details>

## Local development

See **Quick start** above to run the app (`./dev.sh`, or the two processes
manually). Python is 3.12 via [`uv`](https://docs.astral.sh/uv/).

Tests:

```bash
.venv/bin/python -m pytest -q          # backend
cd frontend && npx tsc -b              # frontend typecheck
```

## Deployment

Frontend and backend deploy as two processes; the frontend is static files, the
backend is an ASGI app.

**1. Build the frontend** (static bundle in `frontend/dist/`):

```bash
cd frontend && npm ci && npm run build
```

Serve `frontend/dist/` from any static host, or `npm run prod` for a local
production preview. Point `/api` at the backend (reverse-proxy or an API base
URL). The app uses client-side routing (react-router), so the host must fall
back to `index.html` for unknown paths (e.g. a direct load of
`/estimates/abc123`) — `npm run prod`'s `vite preview` does this
automatically; check your host's docs for the equivalent (CloudFront custom
error responses, Nginx `try_files`, Netlify `_redirects`, etc.).

**2. Run the backend** (no `--reload` in production; use multiple workers):

```bash
uv pip install -e .            # or: pip install .
uvicorn architect_iq.api.app:app --host 0.0.0.0 --port 8000 --workers 4
```

Set `FATHOM_CORS` to the frontend origin, provide `.env` (or real env vars)
with `ANTHROPIC_API_KEY` and a persistent `FATHOM_DB` path (mount a volume so
estimates and rate cards survive restarts — this is the memory that improves the
model over time). Put both behind TLS.

**Notes**
- SQLite suits a single backend instance / small team. For multi-instance, move to
  Postgres behind the same repository interface (`persistence/`).
- The engine runs fully without an API key (deterministic path); add the key to
  enable the LLM features.

## Skills

[`skills/`](skills/) holds standalone Claude Skills that pair well with Fathom
without being merged into it — loosely coupled, not app dependencies. See
[`skills/README.md`](skills/README.md) for the convention and what's there.

## Not yet built (later phases)

The `architectiq` CLI, xlsx/summary emitters, the Claude skill wrapper, and deeper
per-item sizing. See DECISIONS.md D11 for remaining skeleton-depth items.
