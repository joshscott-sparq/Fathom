# DECISIONS.md

Log of judgment calls made during the Architect.IQ build that the spec
(`architect-iq-context.md`) did not fully cover. Each entry: the call, the
reason, and the spec reference it relates to.

## D1. Repo layout: standalone at root
**Call:** Build the engine at the repository root (`src/architect_iq/`, `tests/`,
`skill/`), not under `packages/architect-iq/`.
**Why:** The spec text (§, §6.2) names `Sparq-Holding-Inc/solutions-labs` with a
`packages/architect-iq/` path, but the actual repo is the standalone
`Architect.IQ`. Owner confirmed on 2026-07-17 to treat it as a standalone repo
deployed as a standalone application.

## D2. Points storage: native per-level, story-point normalization in core
**Call:** `WorkItem` stores its 3-point (R/O/P) estimate in the native per-level
t-shirt scale from §2.2 (Story M = 5, Feature M = 12.5, Epic M = 50). Core
exposes a story-point normalization; the §2.2 table is already story-point-scaled
(Feature M = 2.5 stories, Epic M = 10 stories), so normalization is a direct
read, not a re-scaling. The Epic/Feature multiplier (§2.1) applies to
linked-parameter impact at epic/feature level, not to the base points.
**Why:** Owner wants both workbook fidelity (deterministic mode must match the
sheet) and a story-point measure the delivery teams work in. Storing native keeps
deterministic mode exact; normalizing in core surfaces story points without a
second source of truth. Ref §2.1, §2.2.

## D3. PesWeight seeded at 1.2
**Call:** `variables.yaml` seeds `PesWeight = 1.2` (the value §2.1 states is
verified from the workbook), with the 1.1-1.5 guidance range recorded as metadata.
**Why:** §2.1 gives "PesWeight = 1.2 (default 1.1, raise to 1.5 with many
unknowns)" — the stated verified value and the stated default differ. The
verified workbook value governs deterministic parity; the range is available for
overrides in the contextualize step. Ref §2.1.

## D4. AvgStoryPts seeded at 9
**Call:** `variables.yaml` seeds `AvgStoryPts = 9`, with default 8 / range 7-10
recorded as metadata.
**Why:** Same stated-value-vs-default pattern as D3. §2.3 gives "AvgStoryPts = 9
... (default 8, range 7-10)"; the verified value governs parity. Ref §2.3.

## D5. Complexity factor library: structure complete, exact severity curves pending
**Call:** `complexity_factors.yaml` encodes all factor families, their category
grouping, the documented severity ladders (§2.4: 0 / -0.25 / -0.5 / -0.75 / -1.0),
and the families that start at -0.25 (integrations, security/compliance,
staffing difficulty). Every value is flagged with provenance
`default-ladder-pending-A44:C152`.
**Why:** §2.4 describes the ladder and exceptions but does not transcribe the
per-family values from `RiskLookups!A44:C152`. Because the library is data
(design goal: adding/correcting a factor is a data edit, no code change), the
exact values can be dropped in later with zero code impact. FLAGGED to owner.

## D6. Factor family count (27 vs enumerated 29)
**Call:** Encoded the families as enumerated from §2.4 prose. §2.4 states "27
factor families" but the prose enumerates ~29 depending on how compound entries
("schedule/scope/cost flexibility", "data availability/quality") are split.
**Why:** Needs the workbook family list to reconcile exactly. FLAGGED to owner.
Correcting is a data edit. Ref §2.4.

## D27. Skill-authored flags (spec-iq's gap/conflict markers) recognized by exact text pattern, not a general skill protocol

**Call:** Added `core/llm.py::_classify_skill_flag()`, checked first by both
`classify_kind()` and `heuristic_classify_kind()`. It matches spec-iq's exact
authored marker text — `⚑  Gap: ...` and `⚠  Conflict: ...` (the literal strings
`skills/spec-iq/generate-prd.js`'s `gapFlag`/`conflictFlag` render into the
`.docx`, which survive as plain text through Fathom's existing extraction) —
and routes a gap straight to `assumption` and a conflict straight to `risk` at
0.95 confidence, skipping the LLM call and the signal-matching heuristic
entirely. This is a hardcoded recognizer for one skill's specific output
format, not a general "skills can emit routable flags" protocol or a
convention documented anywhere a skill author would discover it — a
differently-worded flag (a different skill, or a future spec-iq version that
changes its marker text) simply won't match and falls through to normal
classification, no error, no silent misroute.

**Why:** `skills/` (see `skills/README.md`) intentionally keeps skills
decoupled from Fathom — no shared code, no dependency either direction. This
recognizer is the one deliberate exception, justified because the alternative
is worse: without it, a spec-iq-flagged gap or conflict is just another
sentence to `classify_kind`, competing on signal words against every other
kind with no privileged treatment — spec-iq's authors already did the work of
saying "this is explicitly unresolved," and re-inferring that from prose
would sometimes get it wrong where the source was already certain. Owner
asked for the LLM layer to be "skill aware" after reviewing spec-iq as a
candidate `skills/` addition.

**What's deliberately left undone:** if more skills adopt a similar
flagging convention, this should generalize into something skills declare
(e.g. a small marker-format registry) rather than accreting one bespoke
regex pair per skill in `core/llm.py`. Not built now because there's exactly
one skill and one marker format to support — premature to design the
registry's shape from a sample size of one.

## D26. D25's classifier wired to routing; pinned_work_items to survive rebuild-from-scratch recalcs
**Call:** Wired D25's `classify_kind` into the Requirements-tab drop flow (previously
deferred). Dropping a file/URL now: (1) adds exactly one Requirements entry — a
2-5 bullet summary of the document, not the raw dump or a per-sentence list; (2)
classifies every decomposed sentence and routes it — `risk`/`assumption`/
`accelerator` become an entry in that tab (same as typing one by hand), `epic`/
`feature`/`story`/anything else become a work-item line in the Estimate grid
(default `feature`; `story` only via the "As a... I want..." template or an
explicit epic/story classification; `epic` only when the model says so). A
batched `group_into_epics` call clusters related features under a shared epic
name describing what they're about — never the source filename. Each item's
short `title` becomes the grid cell; the full original sentence is preserved in
the new `WorkItem.notes` field so detail isn't lost to a terse label.

Getting the routed work items to actually *stick* required a second fix:
`recalculate_from_context` (the Context Panel's debounced auto-recalc) always
rebuilds `work_items` from scratch from the PRD text — it has no way to know
about a manually-classified item that isn't derivable from that text. Appending
such items in the one save that added them isn't enough: the very next
Context Panel edit (anywhere — a different tab, a different field) triggers
this same recalc again and silently discards them, since a fresh rebuild has
no memory of the previous one's append. Fixed by storing them in a new,
persisted `ContextPanel.pinned_work_items` field instead of a one-shot request
param — every recalc re-appends `panel.pinned_work_items` after rebuilding, so
they survive any number of subsequent unrelated saves, the same way a
Requirements entry itself does (it's part of the panel that's resent every
time). Verified via a live test: dropped a PRD, then made a second, unrelated
edit (added an assumption) — the work-item count held steady across both saves
and a full page reload.
**Why:** Owner asked for the routing (previously D25 left as a deferred
decision) and specifically named the epic-naming/notes-preservation and
risk/accelerator/assumption-routing requirements across several follow-up
messages. The rebuild-discards-manual-items tension is a known pre-existing
gap (also affects D24's hand-editable grid — editing a row, then editing any
Context Panel field, discards the hand-edit the same way) that `pinned_work_items`
solves only for classifier-routed items, not general hand-edits; flagged as a
remaining gap, not solved here.

## D25. Kind-classification model built as a standalone function, not yet wired to routing
**Call:** Added a semantic classifier (`core/llm.py::classify_kind` /
`heuristic_classify_kind`) that takes one extracted sentence and scores it
against an owner-supplied taxonomy (`data/estimate_kinds.yaml` →
`models/kinds.py::KindTaxonomy`) of 8 kinds — epic/feature/story/story_point
(work items), risk/assumption (register items), accelerator (modifier), and
phase (timeline container) — each with a definition, pairwise disambiguation
rules against confusable kinds, and keyword/pattern signals. Same
LLM-primary-with-deterministic-fallback shape as `extract_new_requirements`:
the LLM path uses the taxonomy's definitions/disambiguation verbatim as
context; the heuristic path word-boundary-matches each kind's literal signals
(with an explicit regex check for the "As a ... I want ..." story template,
since that signal is a placeholder pattern, not real text to substring-match)
and defaults to "feature" — the taxonomy's closest general "this is scope to
build" kind — when nothing scores above zero. This function is intentionally
**not yet called anywhere** — it's the classifier itself, not the routing that
would use it (e.g. auto-filing a dropped document's sentences into
Requirements/Risks/Accelerators/Assumptions tabs, or into the WorkItem
epic/feature/story hierarchy, by kind). That's a separate, larger integration
decision (it changes established per-tab drop behavior) deferred until asked
for.
**Why:** Owner asked "can you create the model" after supplying the taxonomy
directly (`estimate_kinds.yaml`, 2026-07-23) — the ask was for the
classification model itself, not (yet) for rewiring the Context Panel's
extraction flow around it.

## D24. Estimate work breakdown is a directly hand-editable grid; complexity factors merged into Risks as read-only
**Call:** The "Estimate (work breakdown)" section is now a full CRUD grid
(Level/Epic/Feature/Story/Points R-O-P/Phase/Practice, add/remove rows) that
saves via the existing generic `PUT /api/estimates/{id}` (`update_estimate`,
new version each save) rather than the Context Panel's auto-recalc path — edits
here are direct hand-edits to the work breakdown itself, not context that
regenerates it, so they shouldn't be silently overwritten by the next
requirements-driven rebuild. `WorkItem` gained a `phase_id` field (nullable, no
migration needed) so a row can link to a Context Panel Phase; the dropdown
lists `context_panel.phases`. New rows default to story level with placeholder
text and a manually-flagged `CureAssessment`/`extraction_confidence=1.0` since
those fields are otherwise populated by the extraction pipeline. Complexity
factors, by contrast, stayed read-only and moved into the Context Panel's Risks
tab (a block above the Risks grid) rather than becoming editable — they're
derived output of `core/factors.py::derive_factors()` from context/risks, not
raw user input, so true CRUD doesn't apply to them the way it does to a
hand-entered risk or a work-item row.
**Why:** Owner pointed at the legacy Cutsforth workbook's `Estimates` tab
(Epic/Feature/Story/Points/Phase/Practice grid) as the missing piece — the app
produced every downstream artifact (cost, team, timeline) but never surfaced
the line-item breakdown itself for review or hand-tuning, and asked
specifically for Epic/Feature/Story-level estimation with a Phase link. Ref
CLAUDE.md's Solution Graph section (WorkItem = "one row of the Estimates
grid").

## D23. AI Tiers replace the 3-model dev-model library
**Call:** Replaced the old 3-key dev-model library (traditional/ai-assisted/
agentic) with a 5-tier AI Tier ladder (`tier-1`..`tier-5`), each carrying a
human:AI-agent ratio, a human role, and an AI role (owner supplied the ratio
table). Same data file (`data/dev_models.yaml`), same loader
(`data_loader.load_dev_models`) — only the keys and fields changed, so
`core/scenarios.py` and `core/advisor.py` needed no structural changes beyond
updating hardcoded key references ("traditional"/"agentic" -> "tier-1"/highest
tier). `default_scenarios()` is now data-driven off the tier list (one scenario
per tier at US, plus Nearshore and 50/50-blend variants of the top tier) instead
of 4 hardcoded entries. The Deal-shaping panel's free-form 0-50% AI-boost slider
is replaced by a Tier 1-5 picker that sets the same underlying `ai_boost` lever;
a new `GET /api/ai-tiers` endpoint (renamed from `/api/dev-models`, which had no
callers yet) serves the ratio/role data for that picker and a reference table in
the Team plan section.
**Why:** Owner supplied an AI Tiers table (Tier 1-5, human:AI ratio, human role,
AI role) and asked to add it to the staff/team modeling area, confirming: (1)
replace the 3 dev models with 5 tiers everywhere they're used — scenario
comparisons and the Deal-shaping slider — rather than adding tiers as a separate
concept; (2) derive AI-boost/effort-multiplier values heuristically for now
rather than block on exact percentages. **The tier -> ai_boost mapping is a
first-pass heuristic, not calibrated data:** tier-1=0%, tier-2=15%, tier-3=30%,
tier-4=45%, tier-5=60% boost (effort_multiplier 1.0/0.97/0.90/0.80/0.65),
monotonic with each tier's AI-agent ratio (0/0/1/5/20) and anchored so tier-3
sits near the old "agentic" model's 35%/0.85. FLAGGED to owner: revisit once
delivered actuals exist per tier (the memory/prior-tuning loop is the natural
place to recalibrate).

## D22. Context Panel (context-panel-spec.md)
**Call:** Built the Context Panel as a bottom-docked, collapsible tabbed strip
below the Output Zone (the estimate view), per the spec. Six fixed tabs
(Requirements, Phases, Risks, Accelerators, Assumptions, External Sources); each
context tab is a list of discrete entries added via manual text, dropped file, or
URL; Risks/Accelerators/Assumptions carry a Scope (entire estimate or a phase).
Model: `models/context.py` (ContextEntry, ContextPhase, ExternalSource,
ContextPanel) stored on the SolutionGraph. `PUT /api/estimates/{id}/context`
saves the panel and **auto-recalculates in place** (owner chose automatic-on-
change; frontend debounces ~1s). `POST /api/ingest/url` fetches + strips a URL.
Requirements form the PRD (falling back to the estimate's existing requirements
when the panel has none, so editing only risks/assumptions preserves scope);
risks become velocity-reducing factors; accelerators offset the penalty;
assumptions are recorded. SparqOS is a default read-only external source, always
present. External sources are configurable with stubbed data pull (real clients
when creds exist); SpecKit write-back is user-triggered. Collapse state persists.
**Why:** Owner supplied context-panel-spec.md and confirmed: auto-recalc on
change, external sources configurable + stubbed, SpecKit write-back user-
triggered, build now. Phase-assignment of work in the Output Zone and live
external-source pull remain follow-ups.

## D21. Estimation methodology upgrade
**Call:** Four changes make the estimate responsive and its ranges defensible:
1. **Complexity/risk factors now move the number** (`core/factors.py`). Factors
   are derived from inputs (integration count, compliance posture, tech
   familiarity, legacy signals, the matched pattern's risk families), mapped to
   library impacts (§2.4), summed into a ComplexityImpact that reduces per-engineer
   velocity (§2.3), floored at -70% of AvgStoryPts. Stored on the graph and shown.
2. **Correlated Monte Carlo.** A per-iteration lognormal systemic factor (mean 1)
   multiplies the whole project so summing items no longer collapses the range;
   sigma grows with factor count/severity and top-down/bottom-up divergence.
3. **Confidence-driven spreads** (`_three_point`). Lower sizing confidence widens
   the optimistic/pessimistic band (pessimistic faster).
4. **Blend + decompose.** The reconciliation produces a confidence-weighted blend
   of top-down and bottom-up (the working number); divergence widens the range.
   Large features decompose into story children for a finer bottom-up rollup.
   The MC distribution is recentred on the blend (bottom-up gives the shape, the
   blend gives the level) so effort/duration/cost stay coherent.
Applied consistently in build, recompute, and scenarios.
**Why:** Owner asked to improve the estimation methodology and selected all four
improvements. The complexity library and pattern risk families were previously
inert; ranges were unrealistically tight; confidence and divergence were unused.

## D20. UI: light/dark, avatar, top-bar menus, share-at-top, collapsible, tags
**Call:**
- **Theme:** light/dark via Tailwind class strategy; neutral tokens
  (canvas/surface/field/line/ink/muted) flip under `.dark`, brand accents don't.
  Toggle in the avatar menu, persisted, defaults to OS preference. Always-dark
  surfaces (top bar, login) use fixed `text-white`, not flipping tokens.
- **Avatar:** orange circle with the user's white capitalized initial.
- **Top bar:** hamburger menu (role-filtered nav) + avatar dropdown ("Signed in
  as", light/dark toggle, sign out) at top-right.
- **Sharing at top:** a "Share" button in the estimate header opens a
  Google-Drive-style popover (share by email/name, permission, public link);
  comments moved to the bottom.
- **Collapsible sections:** estimate sections expand/collapse on header click.
- **Tags:** editable metadata tag bar at the top of an estimate; tags persist on
  the graph and surface in list summaries.
- **Rate-card deliverable:** digested the CURRENT RATES sheet into
  `examples/sparq-current-rates.{md,csv}` (+ `-hourly.csv`). The image values are
  hourly bill rates; the loadable CSV uses day_rate = hourly x 8 (engine treats
  the rate column as per working day).
**Why:** Owner asked for Google-Drive-style sharing at top + a hamburger menu,
estimate tagging, expandable sections, comments at bottom, an orange-initial
avatar, light/dark mode, and a CSV/MD rate card from the rates image.

## D19. Live estimation: auto-build, auto-save, clone
**Call:** The estimate editor has no "Generate" button. It debounces input
changes (~900ms) and builds/updates the estimate automatically, saving in place
via `POST /api/estimates/{id}/rebuild` (store `overwrite_latest`, no new version)
so continuous editing doesn't spam versions. Deliberate actions (recompute,
recost, scenarios) still snapshot new versions. `POST /api/estimates/{id}/clone`
copies an estimate into a new one (version 1, "(clone)" suffix) to test other
assumptions; a clone keeps the opportunity link but is never the active/official
estimate (one active per opportunity is preserved). Clients cannot create or clone.
**Why:** Owner asked to drop the Generate button (build from whatever info is
present, update as more arrives), auto-save on every update, and add cloning to
test alternative assumptions.

## D18. Auth, RBAC, domain model, sharing (local login now, OIDC-ready)
**Call:** Added users/roles, an Account -> Opportunity -> Estimate domain model,
estimate sharing, and public links.
- **Auth:** local email+password (PBKDF2, stdlib) issuing JWTs (HS256, PyJWT)
  signed with `FATHOM_SECRET`. Google OIDC endpoints are scaffolded behind
  `GOOGLE_CLIENT_ID/SECRET` (untested in sandbox); JumpCloud slots into the same
  `auth/oidc.py` seam. `.env` loaded via python-dotenv.
- **Roles:** admin (all + manage users/accounts/opportunities/rates), user (owns
  estimates; sees own + shared; training/memory still uses ALL history), client
  (read-only on assigned opportunities). Enforced in `auth/access.py` +
  FastAPI deps.
- **Domain:** an opportunity has many estimates, one `active_estimate_id`
  (official). Estimates carry `owner_id` + `opportunity_id` (store migration adds
  the columns). Salesforce account/opportunity IDs and a Notion page ref are
  modeled; Notion notes come from `integrations/notion.py` (stub now, live client
  behind `NOTION_API_KEY`).
- **Sharing:** per-estimate shares at view/comment/edit (by email or by a known
  user's name), public view-only share-link tokens (no login, `/shared/{token}`),
  and comments (comment/edit permission). Effective permission = max of
  role/ownership/assignment/share.
- **Sample logins** seeded (admin/user/client, see README) for now; production
  sets `FATHOM_ADMIN_PASSWORD` and rotates.
**Why:** Owner asked for a login with three roles, the SF/Notion-linked domain
model, estimate sharing at three permission levels with public view-only links,
sharing by email or name, sample per-role logins, and Google/JumpCloud SSO.

## D17. Multiple saved rate cards (one active, one default)
**Call:** Rate cards are persisted in SQLite (shared DB): multiple named cards,
exactly one active, one default (seeded from the placeholder pricing file). The
active card feeds estimate build, re-cost, and scenarios. Default cannot be
deleted; deleting the active card reverts to default. Cards hold
(discipline, tier, location, day_rate) rows.
**Why:** Owner asked for multiple saved cards with one active and one default,
each carrying role/location/rate — replacing the earlier single in-memory card.

## D16. Scenarios + optimization advisor
**Call:** Each estimate can compute multiple named scenarios (Scenario +
ScenarioResult) over the same work breakdown: development model (traditional /
ai-assisted / agentic, from `dev_models.yaml` — ai_boost + effort_multiplier) and
location mix (US / NS / blended, via RateCard.blended_rate). An advisor
(`core/advisor.py`) suggests cheaper/faster team models (computed for real
numbers) and features to defer to a later release, LLM-primary with heuristic
fallback, grounded in historical estimates (reference class) so it improves as
engagements accumulate.
**Why:** Owner asked that each estimate handle multiple staffing/development
models with assumptions, that the LLM suggest cheaper/faster team models and
deferrable features, and that historical estimates train the suggestion engine.

## D15. LLM ingest/matching + .env; cost model
**Call:** LLM layer (`core/llm.py`, injectable client) does requirement
extraction, capability derivation, and pattern ranking; each falls back to a
deterministic heuristic on no-key/error. Enabled by `ANTHROPIC_API_KEY` (loaded
from `.env` via python-dotenv); `FATHOM_DISABLE_LLM` forces the heuristic
path, `FATHOM_LLM_MODEL` overrides the model. Team velocity now scales
sub-linearly with headcount (`core/velocity.py`, Brooks exponent 0.85) and the
engineer-count knob scales team allocations, so adding engineers shortens the
timeline without looking strictly cheaper (fixes the D11 bug).
**Why:** Owner asked to wire the LLM layer, add an env setting for the API key,
and fix the engineer-count cost model.

## D14. Frontend styling: Tailwind CSS v4
**Call:** Frontend uses Tailwind CSS v4 (via `@tailwindcss/vite`), with the Sparq
brand palette declared as `@theme` tokens (`brand-orange`, `brand-green`,
`brand-aurora`, etc.) so utilities like `bg-brand-orange` carry the brand. A few
repeated widgets (`card`, `btn`, `field`, `badge`) stay as `@apply` component
classes; everything else is utility classes in JSX.
**Why:** Owner set the stack constraint "React or Vue with Tailwind" for the
frontend, "Node or Python" for the backend. React + FastAPI already complied; the
hand-rolled CSS was migrated to Tailwind to meet the styling requirement.

## D13. Loadable rate cards for leverage modeling
**Call:** Rate cards (roles + rates) are loadable at runtime (CSV/XLSX/YAML) via
`POST /api/rates`, held as the active card in the service, and used for new
estimates and for re-costing existing ones (`POST /api/estimates/{id}/recost`).
Re-cost holds effort and duration fixed and only re-derives role rates,
monthly/total cost, and the cost distribution (rates don't change the work).
Committed example cards live in `examples/` (onshore vs blended leverage).
**Why:** Owner wants to model different leverage models, teams, and prices.
Changing team tier/location mix (beyond re-pricing fixed roles) is a further
lever noted for later; the current card reprices the fixed team composition.

## D12. Demo mode gated by Vite run mode
**Call:** Demo mode is a distinct frontend run mode, not always-on. `npm run demo`
(= `vite --mode demo`, loading `.env.demo` with `VITE_DEMO_MODE=true`) enables it;
`npm run dev` and `npm run prod` do not. In demo mode the app auto-seeds curated
sample data on load (idempotent) and lands on the estimates list, so every
feature is immediately testable with dummy data; a "Load demo data" button also
re-seeds on demand. Demo estimates are name-prefixed `[Demo]`; outside demo mode
the list filters them out client-side, and the backend `POST /api/demo/seed`
endpoint stays available but is only invoked by the demo frontend. Backend demo
seeding lives in `architect_iq/demo.py` (also runnable headless via
`python -m architect_iq.demo`).
**Why:** Owner asked that demo show only under `npm run demo`, and that demo mode
always serve as a full sample sandbox exercising every function. Frontend-flag
gating + client-side `[Demo]` filtering honors both without backend mode
coupling. The `[Demo]` prefix filter is a skeleton approach; a persisted
demo/sample flag on the estimate would be cleaner if this grows.

## D11. Known skeleton gaps (to close when deepening the math)
Surfaced during the full-stack slice verification (2026-07-17). All are
skeleton-depth simplifications, not final behavior:
- **Recompute cost vs headcount:** the `engineer_count` knob raises velocity
  (shortens duration) but does not add those engineers' cost to the monthly burn,
  because the team table roles are unchanged. Result: adding engineers currently
  looks strictly cheaper. Fix when deepening: grow role allocations with
  engineer_count so monthly cost scales with the team, and model the
  points-per-engineer diminishing return (Brooks). Until then the cost knob is
  directional only.
- **Capability derivation is 1:1 with components** (skeleton), not true
  higher-level capabilities. Replace with LLM-derived capabilities.
- **Requirement extraction is line-based**, confidence fixed at 0.5. Replace with
  the LLM ingest step (§3.1) that sets real per-item confidence.
- **Pattern parametric values are starter calibration**, tuned only by the
  shrinkage prior once real estimates/actuals accumulate.
- **LLM matcher not yet wired**; deterministic signal-overlap match is the only
  path running. LLM match is the planned primary when a key is present.

## D10. Deterministic (workbook) vs Monte Carlo values diverge by design
**Call:** Keep both a deterministic point estimate (workbook weighted mean, §2.1,
with PesWeight 1.2 / OptWeight 0.95) and the PERT-beta Monte Carlo distribution
(lambda=4). They are different methodologies and will not agree: the workbook
weighting is pessimism-loaded, so its mean can exceed the MC P90. Label them
distinctly in the UI; do not force the MC distribution to re-center on the
workbook value. The gap is treated like the top-down/bottom-up gap — a signal for
the critique pass, not an error. Cost/monthly formula also departs from the literal
§2.6 "DayRate * WorkingMonthDays * 8": rates in our schema are per working day, so
monthly = day_rate * WorkingMonthDays (the sheet appears to store an hourly rate).
**Why:** §3 originally required deterministic mode to match the workbook exactly,
but the workbook is now calibration-only (D8), and §4.1 makes Monte Carlo the
primary output. Surfacing the divergence is more honest than hiding it. Revisit
lambda / weighting during the Phase 4 calibration loop against actuals.

## D9. Full-stack app: UI + persistence + memory pulled forward
**Call:** Architect.IQ is a full-stack application, not a skill emitting a static
artifact. Stack: React + TypeScript (Vite) frontend, FastAPI backend, SQLite
persistence (behind a repository interface, swappable to Postgres). The Python
engine remains the core, wrapped by the API. Estimates persist as versioned
Solution Graphs (every edit is a new version), enabling interactive editing.
Memory = reference-class retrieval (find similar past estimates to seed priors up
front) + pattern-prior tuning (past estimates and, later, actuals refine
parametric costs). The `PatternPrior` and actuals-ingestion extension points
become real components rather than stubs. Build sequence: full-stack skeleton
first (thin vertical slice across all layers), then deepen the estimation math.
**Why:** Owner confirmed on 2026-07-17 wanting drag-and-drop + manual context
entry, interactive estimates, persistence that improves over time, and feeding
prior estimates into memory to learn up front. This pulls Phase 4 (calibration)
and Phase 5 (hosted UI) forward and supersedes the §5 architecture decision and
the §5.3 "interactive artifact instead of an app" middle ground. Chosen via
explicit options: React+FastAPI / full-stack skeleton now / SQLite / retrieval +
prior tuning.

## D8. Pivot: architecture-first, workbook as calibration reference only
**Call:** Reorient Phase 1 around the Solution Graph (§4.3) as the central object,
with reference-architecture generation leading and effort/cost flowing from the
architecture. The workbook math (§2) is demoted from binding contract to
calibration reference: its t-shirt scale, ratios, and rates become defaults and a
sanity-check, but the engine does not replicate its exact formulas or treat the
xlsx as the primary deliverable. The pattern library (§4.2) is pulled forward
from Phase 2 to serve as the spine. Two-sided reconciliation (top-down pattern
cost vs bottom-up work-item rollup) is now in Phase 1 scope.
**Why:** Owner confirmed on 2026-07-17 that the workbook was a past constraint,
not the goal; the real objective is generating reference architectures, cost
models, and effort estimates from requirements plus client context. Owner chose
"reference & calibration only" for the workbook and "architecture-first (Solution
Graph)" as the Phase 1 center of gravity. This supersedes the original
build-order framing in the task brief (which said replicate §2 exactly first).
Step 1 domain models (WorkItem, complexity factors, phases, team, variables) are
retained; the flat EstimateModel is replaced by SolutionGraph.

## D7. Python toolchain via uv, Python 3.12
**Call:** Use `uv` to provide Python 3.12; system Python is 3.9.
**Why:** Spec requires Python 3.12 (§build constraints); only 3.9 is on the
machine and `uv` is available to pin 3.12 without touching system Python.
