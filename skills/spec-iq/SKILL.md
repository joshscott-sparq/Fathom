---
name: prd
description: >
  Use this skill to create, scaffold, or fill in a Product Requirements Document (PRD).
  Trigger whenever the user mentions PRD, product requirements, feature spec, product spec,
  requirements document, or asks to define/document what to build for a product or feature.
  Also trigger when a user says "write up the requirements for X", "I need a spec for X",
  "help me document this feature", or any similar phrasing. The skill produces a fully
  formatted, pre-filled .docx PRD based on context the user provides about their product,
  problem, or feature — either a live description or source material such as a
  transcript, notes, or a document.
---

# PRD Skill

Produces a professional, formatted, pre-filled Product Requirements Document as a
`.docx` file. Every PRD this skill produces is pre-filled — there is no blank-template
mode to choose. The skill always runs an intake process (Step 2) and drafts from what
it learns there, whether that's a document or transcript the user provides, or a live
description of the product.

**Why this matters for consistency:** if two different people run this skill on the same
source material, the goal is that they get the same structure and the same required
fields filled — not necessarily identical wording, but never a document where one
person's draft quietly invents a number the other flagged as unknown, or where one
draft ships with generic placeholder content the other replaced. The rules below exist
to make that true.

---

## File architecture — read this before editing anything

This skill is split into two files on purpose:

- **`generate-prd.js`** — fixed structure and rendering code. Section order, headers,
  table layout, column widths, colors. **Never edit this file to personalize a PRD.**
- **`prd-content.js`** — every piece of content that varies between PRDs: the problem
  statement, KPI rows, personas, requirements, stakeholders, etc.

**To personalize a PRD, edit only `prd-content.js`.** This split is what keeps two
independently-generated PRDs from the same input structurally identical — content
edits can't accidentally also reword a section header or change table structure,
because content and structure live in different files.

---

## Workflow

### Step 2 — Intake

Every PRD runs through this same intake process — there is no mode to choose. The only
thing that varies is *how* questions get asked (see Step 2.3), and that depends on
whether the user has given you source material to draw from.

#### Step 2.1 — Establish the hard-gate fields

Two fields are required before any drafting starts: a **named author** and a usable
**problem statement** (1–2 sentences covering who's affected and what the problem is).
If either is missing from what the user has given you, ask for it directly and
immediately — regardless of which intake branch below applies. These are hard gates:
nothing in Step 2.2 or 2.3 can route around a missing required field.

- **Author / team name** — the specific person's name (and initials) authoring this
  draft. This fills the cover page's Author(s) field and is also needed for the output
  filename (see Step 5) — never leave this as the "Name, Title" placeholder.
- **Problem statement** — who experiences it, how often, what's the cost of not solving
  it. If the user hasn't said this yet, ask before doing anything else.

#### Step 2.2 — Score intake readiness

Score the information gathered so far (the source material, or the user's answers up
to this point) against the readiness rubric in `scorecard-config.js`. This step is now
live — real scoring, not the Changeset 2B placeholder.

**How to score:** for each of the 13 statements in `scorecard-config.js`'s
`STATEMENTS` array, judge the available information against that statement's three
anchors (Absent / Vague / Specific) and assign 0, 1, or 2. Then call
`scoreIntake({ statementScores, hardGates })` — `statementScores` is your 13
judgments keyed by statement id; `hardGates` is `{ authorNamed, problemStatementUsable
}`, reflecting whatever Step 2.1 actually resolved (this is a direct read of Step 2.1's
outcome, not a re-scoring of statement #12 or statements #1/#2). The function returns
per-category subtotals, a total expressed as a percentage of achievable points, and a
band — see the comment above `scoreIntake` in `scorecard-config.js` for the exact
return shape.

**Show the scorecard to the user, in chat.** This is an informational signal, not a
silent computation — render it as a short table: category, score, band. If the user
asks why a category scored the way it did, `CATEGORY_BARS` in `scorecard-config.js`
documents how that category's bar compares to the completeness rubric's bar (see
"Scorecard vs. completeness rubric" below).

**The band is advisory, never a blocking gate.** "Leave it as a gap" is always a valid
response, at any score, and drafting is never refused. If the band comes back "Not
Enough to Start" — either because points are below 50%, or because a hard gate (named
author, or a usable problem statement) is unmet regardless of points — say so plainly
and offer the user a choice: answer the weakest-scoring categories now, or draft anyway
with the gaps flagged. Whichever they choose, proceed to Step 2.3 — there is no
scenario in which scoring blocks drafting.

**Capture this score.** The scorecard you show here is not just displayed and
discarded — record the full `scoreIntake()` result (or enough of it to reconstruct the
table you showed) into `prd-content.js`'s `preDraftScorecard` field before moving on.
A later change (Changeset 3B) will carry this captured value forward *verbatim* into a
rendered Appendix D "Pre-Draft" column — Appendix D will not recompute the pre-draft
score at delivery time, so what you capture here is what a reader ultimately sees as
"where intake started." Changeset 3B is not built yet: `preDraftScorecard` is only a
holding field for now, with nothing downstream reading it.

**Scoring covers six categories; gap-asking covers all of them.** The 13 statements
span only the six scored rubric categories (1.1, 1.3, 2.1, 3.2, 6.1, 6.2). The PRD has
roughly 18 sections total, each with its own `gaps` array. Scoring exists to focus
*which weak spots to prioritize surfacing* in Step 2.3 — it does not replace or narrow
the full gap sweep. Every section that can't be filled still gets a gap question in
Step 2.3, scored or not; see "Both branches, always" below.

#### Step 2.3 — Resolve gaps and conflicts

A **gap** is missing information ("what's the answer?"); a **conflict** is
contradictory information ("which of these two is right?") — two different launch
dates in one transcript, a requirement that contradicts another, a revision that
contradicts the prior version. Both get detected and resolved the same way, in the
same pass, with the same in-flow timing rule described below — the only difference is
the question shape: a gap asks the user to supply a missing value, a conflict asks
the user which of the values already given wins. Flag an unresolved conflict with a
distinct `⚠ Conflict:` marker — never the `⚑ Gap:` marker — in `prd-content.js`'s
matching `conflicts` array (see the file's header comment, rule 8, for the shape).
See `docs/scorecard-proposal.md` §E for the full design.

First, determine which of the two branches below applies. They are mutually exclusive —
only one governs a given PRD session. (These were formerly labeled 2a/2b; the behavior
below is unchanged from that 2026-07-15 fix — only the names changed. See README
version history.)

**Source-led intake** (a document, transcript, notes, or meeting recap was provided):
do **not** batch questions upfront. This is the hard gate, and it fully governs this
case — work through the source material section by section, in the order fields appear
in `prd-content.js` (problem statement → business objectives → KPIs → scope → personas
→ requirements → etc.). The moment a field can't be filled from the source, stop and ask
the user about that specific field before moving to the next section — one gap, one
question, asked as it's identified, in the flow of drafting.

Do not compile a full list of gaps and ask them all in a single end-of-processing
message. Do not ask for all missing fields upfront in one batch either — that defeats
the point of extracting from the source as you go, since it's the only way a user's
"leave it as a gap" answer stays anchored to the section it belongs to.

Conflicts are handled in this same section-by-section pass: if two parts of the
source material disagree on a field's value, stop at that point and ask which one
wins before moving on — exactly like a gap, just phrased as a choice instead of an
open question.

**If the user's own instructions ask you to minimize interruptions** (e.g. "just flag
gaps, don't walk me through everything," "don't step me through the whole template"):
read that as permission to stop narrating sections you *can* fill confidently from
source — not as permission to defer genuine gaps to a batched list. A gap is still a
gap; it still gets asked about individually, in flow, before you move past that
section. If a user explicitly asks you to batch every gap into one end-of-session list
anyway, you can do that — but confirm that's what they mean before switching modes,
since it's a deviation from the skill's default and easy to conflate with "don't
over-explain."

**Interview-led intake** (no source material — the user is describing the product
live): there's nothing to work through section by section, so ask a starter set
upfront, in a single message, then handle whatever's still unclear in one consolidated
follow-up round rather than one question at a time:

- **Product / feature name** — unscored, but a draft can't be named without it (see
  Step 5).
- **Problem being solved** (rubric 1.1) — role, frequency, cost of inaction; also the
  Step 2.1 hard gate for the problem statement itself.
- **KPIs** (rubric 1.3) — at least one metric with a baseline, a target, and a
  timeframe.
- **Personas** (rubric 2.1) — the primary end user, distinct from whoever's authoring
  this PRD.
- **Functional requirements** (rubric 3.2) — what the product must do, each with a
  rough priority signal.
- **Milestones** (rubric 6.1) — a target date (ISO 8601, `YYYY-MM-DD`) or quarter (e.g.
  "Q3 2026" — see the date-specificity extraction rule below), plus whether
  engineering/design has weighed in.
- **Stakeholders** (rubric 6.2) — who owns and signs off; also the Step 2.1 hard gate
  for the author specifically.
- **What's out of scope** — asked directly; see the in-scope/out-of-scope note below.

This starter set intentionally does not cover every PRD section. Most sections (edge
cases, integrations, decision log, business objectives, user stories, data & privacy,
and more) are unscored and are **not** asked upfront — they flow through the normal gap
mechanism during drafting instead, exactly as in source-led intake.

Once intake-readiness scoring (Step 2.2) is fully built, the follow-up round above is
intended to be driven by that score — targeted at whichever categories scored weakest,
rather than a generic sweep. Until then, treat the follow-up round as covering whatever
from the starter set above is still unclear or thin.

Any conflicts noticed among the upfront answers (e.g. the user gives two different
values for the same thing across their own answers) are resolved in this same
consolidated follow-up round as remaining gaps — not asked about individually during
the upfront round.

**In-scope vs. out-of-scope — why only one is asked directly.** Do not ask "what's in
scope?" as its own question in either branch. In-scope is *derived*: once the user has
described the problem and the functional requirements, synthesize a draft in-scope list
from what they already told you, reflect it back, and ask them to confirm or correct
it — that's the only "in-scope" question, and it's a confirmation, not an open question.
Out-of-scope is *asked directly*, because it almost never surfaces unless someone asks
for it. Frame it like: *"From what you've described, the in-scope work looks like [X,
Y, Z]. What's deliberately out of scope — things people might assume you're building
but you're intentionally not?"* This asymmetry is intentional, not an oversight — see
also the `scope.inScope` / `.outOfScope` note in Step 3.

**Both branches, always:**

- **All gaps get asked about, not just the categories covered above.** The PRD has
  roughly 18 sections, each with a `gaps` array. Every section that can't be filled
  still gets a gap question, whether or not it was part of an upfront starter set.
- **"Leave it as a gap" is always a valid answer** to any individual question — that's
  not a reason the question shouldn't have been asked.
- **Conflicts get the same treatment as gaps.** Detect contradictions as you go, flag
  them with `⚠ Conflict:` (distinct from `⚑ Gap:`), and ask which value wins at the
  point you notice it. **"Leave it unresolved" is a valid outcome**, just like a gap —
  the conflict then stays visible in the delivered draft as an unresolved `⚠ Conflict`
  flag, and pulls that category's Appendix D post-draft score down the same way an open
  gap does.
- **Drafting is never blocked.** What's not fine is generating the document first and
  only listing gaps afterward, or batching every gap into one end-of-processing message
  instead of asking as you go (source-led) or in the single upfront/follow-up rounds
  (interview-led).

### Step 3 — Fill in `prd-content.js`

Copy `generate-prd.js` and `prd-content.js` to your working directory together — they
must stay paired. Edit **only** `prd-content.js`:

- `cover` — product name, authors, dates, footer label
- `problemStatement.text` / `.gaps`
- `businessObjectives.bullets` / `.gaps`
- `kpiRows` / `kpiGaps`
- `scope.inScope` / `.outOfScope` / `.gaps` — gathered asymmetrically during intake
  (see Step 2.3): in-scope is derived from the functional requirements already
  gathered and reflected back for confirmation, never asked as its own open question;
  out-of-scope is asked directly, since it doesn't otherwise surface. Don't read the
  asymmetry as an oversight.
- `personas.primary` / `.secondary` / `.gaps` — see the persona-definition rule below
- `userStoryRows` / `userStoryGaps`, `currentWorkflowRows` / `currentWorkflowGaps`
- `requirementRows` / `requirementGaps`, `nfrRows` / `nfrGaps` — see the section-placement rule below
- `designReferences.bullets` / `.gaps`, `userFlows` / `userFlowGaps`, `edgeCaseRows` / `edgeCaseGaps`
- `constraintsRows` / `constraintsGaps`, `dataPrivacy.bullets` / `.gaps`, `integrationPoints.bullets` / `.gaps`
- `milestoneRows` / `milestoneGaps` — see the date-specificity rule below
- `stakeholderRows` / `stakeholderGaps`, `questionRows` / `questionGaps`, `decisionRows` / `decisionGaps`
- `versionHistoryRows`, `glossaryRows` — self-referential to this document (this draft's own revision history; terms already used in the document itself), not derived from the source material, so no gaps array
- `relatedDocuments.bullets` / `.gaps` — links to other documents (roadmap, research, architecture); IS source-derived like design references or integrations, so it has a gaps array like they do
- `sourceAttribution` — one sentence naming what this draft was built from (transcript, date, participants), for traceability

Every section that pulls content from the source material has a matching gaps field —
either `sectionName.gaps` (object-shaped sections) or a sibling `xGaps` array
(row-array sections, e.g. `kpiRows` pairs with `kpiGaps`). Check the field comment in
`prd-content.js` for the exact name before assuming a section has no gaps mechanism.
Every one of those sections also has a matching `conflicts` field (same naming
pattern — `sectionName.conflicts` or a sibling `xConflicts` array) for contradictory
(rather than missing) information — see the gap-vs-conflict distinction in Step 2.3.

Every field has a comment in `prd-content.js` showing the expected shape. Follow it exactly — the render functions expect fixed-length arrays in a fixed order.

#### Extraction rules (apply these while filling in content)

1. **No fabrication.** Never invent a stakeholder, quote, metric, date, or commitment that isn't present in the source material.
2. **Unknown handling.** Any field without direct source support goes in that section's `gaps` array (renders as an orange `⚑ Gap:` flag) — never filled with plausible-sounding placeholder content instead. This applies to KPI targets/baselines/timeframes especially — "TBD — not stated in source" beats a specific-sounding invented number. Every content section (1.1 through 6.4) has a gaps mechanism — check `prd-content.js` for the exact field name (`sectionName.gaps` or a sibling `xGaps` array) rather than assuming a section can't be flagged. (A gap is *missing* information. If instead the source gives *contradictory* values for the same field, that's a conflict, not a gap — see rule 8 and Step 2.3.)
3. **Verbatim fields** (stakeholder names, dates, decisions, direct quotes) must be attributable to the source. Preserve their specificity rather than paraphrasing it away.
4. **Synthesis fields** (problem statement, objectives) may synthesize across the source but must not introduce facts, figures, or names absent from it.
5. **Date specificity.** Preserve the source's own precision. Only convert a relative reference ("early next week") into a calendar date when both the anchor date and the unit are unambiguous from context (e.g., a known meeting date plus "next week" is safe). Do not invent day-level precision from vague terms like "a few days out" or "single-digit days" — preserve that phrasing instead of guessing a date. **Dates are written in ISO 8601 (`YYYY-MM-DD`).** The one deliberate exception is the cover page's `targetLaunch` field, which may instead hold a human-readable quarter (e.g. "Q3 2026") when the source only specifies a quarter — that's intentional, not an oversight to "fix."
6. **Persona definition.** The primary persona is always the end user of the product/feature being described — never the person authoring this PRD. If the author and a plausible end user are the same individual (e.g., a BA building a tool for BAs), define the persona by their *relationship to the product*, not their name.
7. **Section placement.** Non-Functional Requirements (3.3) = qualities the system itself must exhibit (security, performance, compliance behavior). Constraints & Dependencies (5.1) = external limitations on how it can be built (tooling availability, other teams, contracts). When unsure, ask: "is this a property of the system, or a limit imposed on the build?"
8. **Conflict handling.** When the source contains contradictory values for the same field (two different dates, two different owners, a requirement that contradicts another), don't pick one arbitrarily and don't file it as a gap — put it in that section's matching `conflicts` array (same naming pattern as `gaps`) instead, and ask the user which value wins, in flow (Step 2.3). If still unresolved when drafting finishes, leave it there — it renders as a `⚠ Conflict:` flag and pulls that category's Appendix D post-draft level down the same way an open gap does. See `docs/scorecard-proposal.md` §E.

### Step 4 — Generate, strip guidance, self-audit, then validate

```bash
cd /home/claude/prd-skill   # wherever you copied the paired files
node generate-prd.js
```

**Immediately strip leftover guidance text — before doing anything else with the
output:**

```bash
python3 scripts/strip-guidance.py /home/claude/prd-output.docx
```

`generate-prd.js` always emits two visually-identical-looking kinds of orange italic
text. That's legacy dual-purpose rendering machinery — the same renderer used to also
produce a blank template — left in place deliberately rather than removed here (tracked
as cleanup in backlog #40/#41); it does not mean blank-template mode is still offered.
In current use, that machinery only ever produces: `✏` guidance notes ("how to fill out
this section," meant for whoever is authoring the PRD, never for stakeholders) and
`⚑ Gap:` flags (things missing from the source, which must stay visible). As of
Changeset 3C there's a third kind, `⚠ Conflict:` flags (contradictory source
information that's still unresolved, rendered in a distinct color from both of the
above), which must also stay visible. Guidance text left in a stakeholder-facing draft
is a shipped mistake — this script removes every `✏` paragraph and leaves every `⚑`
and `⚠` paragraph untouched. It exits non-zero if it can't confirm all three of those
things happened cleanly. Run it every time; there is no mode in which guidance text is
supposed to stay.

**Then run the self-audit:**

```bash
node scripts/self-audit.js /home/claude/prd-output.docx
```

This checks the generated document's text for known leftover-boilerplate markers (e.g.
"Enter product / feature name", "99.9% uptime SLA", "[Insert link]") — markers left
over from what used to be the blank-template output, now pure failure signals. If it
fails, it prints exactly which markers are still present — go back to `prd-content.js`,
and for each one either fill it in from the source or move it to a `gaps` entry. **Do
not present a PRD that fails this check** — a passing self-audit is what prevents a
document from shipping with generic, uncustomized sections that look finished but
aren't (this is the specific failure mode this rule exists to catch).

Run the self-audit every time; there is no mode in which those markers are expected.

Then validate the document structure:

```bash
python3 /mnt/skills/public/docx/scripts/office/validate.py /home/claude/prd-output.docx
```

### Step 5 — Deliver

Name the output file using this convention, so independently-generated drafts never
collide or get confused with one another:

- **First draft of a product/feature:** `PRD-[ProductName]-[AuthorInitials]-[YYYYMMDD].docx`
  (e.g., `PRD-SoloRecipeBuilder-BA-20260710.docx`) — `YYYYMMDD` is ISO 8601 *basic*
  format (no separators); it's still ISO 8601, just a different valid form than the
  in-document `YYYY-MM-DD` (*extended* format)
- **A revision of an existing PRD (not a new independent draft):** `PRD-[ProductName]-v[#]-[AuthorInitials].docx`
  (e.g., `PRD-SoloRecipeBuilder-v2-BA.docx`) — bump the version number and add a row to
  the document's own `versionHistoryRows` (Appendix A) to match.

```bash
cp /home/claude/prd-output.docx /mnt/user-data/outputs/PRD-[ProductName]-[AuthorInitials]-[YYYYMMDD].docx
```

Then call `present_files`.

---

## Completeness rubric

Beyond the self-audit (which catches leftover boilerplate), check these specific
fields before considering a pre-filled PRD done. If a check fails, it belongs in that
section's `gaps` array — the document can still be generated and shared, but the gap
must be visible, not silently absent.

| Section | Required to be considered complete | If missing |
|---|---|---|
| 1.1 Problem Statement | Names the affected role, frequency, and cost of inaction | Flag as gap |
| 1.3 KPIs | At least one metric with baseline, target, and timeframe | Flag as gap |
| 2.1 Personas | Primary persona identified per the persona-definition rule | Flag as gap |
| 3.2 Functional Requirements | Every requirement has an assigned MoSCoW priority | Flag as gap |
| 6.1 Milestones | At least one milestone with a date or explicit relative timeframe | Flag as gap |
| 6.2 Stakeholders | Named author plus sign-off status for each stakeholder | Flag as gap |

### Scorecard vs. completeness rubric — related, not identical

This rubric and the Step 2.2 readiness scorecard (`scorecard-config.js`) check
different things on purpose. This rubric checks **presence** — is there a persona at
all? a priority? a date? The scorecard checks **presence + specificity/quality** — is
the persona fleshed out with a stated goal? are requirements behavioral, not vague? has
Engineering weighed in on the date? The scorecard is a **strict superset**: this
rubric is the floor, the scorecard is the quality gradient sitting above it. A section
can pass this rubric (something is present) and still score "Vague" on the scorecard
(present, but not specific).

`scorecard-config.js`'s `CATEGORY_BARS` documents this floor-vs-bar relationship per
category explicitly, so a future change to either bar is a visible data edit, not
silent drift between two descriptions of "done" living in two files. Two categories
are stricter on the scorecard than here (2.1 Personas — also requires the persona's
goal/pain be stated; 3.2 Functional Requirements — also requires behavioral, testable
language); 1.3 KPIs and 6.2 Stakeholders match exactly; 1.1 Problem Statement and 6.1
Milestones are the same bar, split/extended into more granular statements. See
`docs/scorecard-proposal.md` §C.1 for the full audit.

---

## PRD Section Reference

Each section of the PRD serves a specific purpose. Here is a quick reference for what belongs where:

| Section | Purpose | Common mistakes |
|---------|---------|-----------------|
| 1.1 Problem Statement | The pain, not the solution | Using solution language; being too vague |
| 1.2 Business Objectives | Company-level goals this serves | Objectives with no measurable tie-in |
| 1.3 KPIs | How you'll know it worked | Vanity metrics; no baseline or timeframe; inventing targets not in the source |
| 1.4 Scope | Explicit in/out boundaries | Vague exclusions; no 'won't have' list |
| 2.1 Personas | Who uses this and why | Made-up personas with no research basis; naming the PRD's author as the persona |
| 2.2 User Stories | Jobs users need to do | Stories without acceptance criteria |
| 2.3 Current Workflow | Where the pain actually lives | Skipping this section entirely |
| 3.1 MoSCoW | Priority framework | Treating everything as Must Have |
| 3.2 Functional Reqs | What the system must DO | Vague language; UI description not behavior |
| 3.3 Non-Functional Reqs | How the system must BEHAVE | Missing performance, security, accessibility; putting tooling/vendor constraints here instead of 5.1 |
| 4.1 Design References | Links to live design files | Embedding screenshots as source of truth |
| 4.2 User Flows | End-to-end paths through the product | Only covering the happy path |
| 4.3 Edge Cases | Non-happy-path scenarios | Skipping entirely — most common failure |
| 5.1 Constraints | Hard limits on implementation | Not flagging third-party dependencies; putting system-quality NFRs here instead of 3.3 |
| 5.2 Data & Privacy | What data is touched; compliance | Missing PII and retention requirements |
| 5.3 Integrations | External systems and APIs | Not including rate limits or auth methods |
| 6.1 Milestones | Agreed delivery dates | Dates without engineering input; inventing day-level precision from vague source timing |
| 6.2 Stakeholders | Who owns and approves | Missing sign-off chain |
| 6.3 Open Questions | Unresolved blockers | Letting questions sit without owners |
| 6.4 Decision Log | Why decisions were made | Not recording decisions at all |

---

## Assets

- `assets/prd-template.docx` — kept as an internal structural reference only (what the
  skeleton looks like); no longer a user-facing deliverable — the skill always
  generates a pre-filled PRD, never hands this file out directly
- `generate-prd.js` — structural rendering code (do not edit to personalize a PRD)
- `prd-content.js` — all editable content, with inline extraction-rule reminders (edit this to personalize)
- `scorecard-config.js` — data-driven config + arithmetic for the Step 2.2 readiness scorecard (the 13 scored statements, category bars, bands, `scoreIntake()`); skill-wide, not per-PRD content — never edit it to personalize a single PRD
- `scripts/self-audit.js` — checks generated output for leftover boilerplate; run before presenting a PRD
- `scripts/strip-guidance.py` — removes leftover `✏` guidance paragraphs from a PRD while preserving `⚑` gap flags and `⚠` conflict flags; run immediately after `generate-prd.js`, before `self-audit.js`
- `scripts/test-strip-guidance.py` — automated fixture test verifying `strip-guidance.py` strips `✏` and preserves `⚑`/`⚠` in both standalone paragraphs and table cells

---

## Tips for High-Quality PRDs

- **Outcomes over outputs** — define what success looks like, not just what to build
- **Every requirement must be testable** — if QA can't write a test for it, rewrite it
- **MoSCoW ruthlessly** — a PRD where everything is Must Have is useless
- **Record decisions with rationale** — prevents relitigating past choices
- **Date and version every revision** — stale PRDs cause more damage than no PRD
- **Delete guidance text before sharing** — automated by `scripts/strip-guidance.py` in Step 4, every time. Orange `✏` notes are for the author, not stakeholders. `⚑ Gap` and `⚠ Conflict` flags are different — those should stay visible to stakeholders until actually resolved, not deleted along with the guidance text.
