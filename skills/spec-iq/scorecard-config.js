// ─────────────────────────────────────────────────────────────────────────────
// SCORECARD CONFIG — data-driven config + scoring arithmetic for the pre-draft
// intake readiness scorecard (SKILL.md Step 2.2) and, later, the Appendix D
// post-draft scorecard (Changeset 3B). Both are meant to read from this one
// file so the two scores can never diverge — see docs/scorecard-proposal.md §D.
//
// WHY THIS IS ITS OWN FILE, NOT A SECTION OF prd-content.js: prd-content.js is
// per-PRD content; this config is skill-wide (shared across every PRD the
// skill produces). Mixing them would reintroduce the content/structure
// entanglement that the generate-prd.js / prd-content.js split deliberately
// avoids. Decided 2026-07-22 — see docs/scorecard-proposal.md, "Decisions" #1.
//
// SCOPE (Changeset 3A only):
//   - The 13-statement v1 scored config (§C.3), each with a category, a
//     statement, three anchor descriptions, a weight, and the per-category
//     "bar" documentation (§C.1).
//   - scoreIntake(): 0/1/2 scoring -> category subtotals -> a total expressed
//     as a PERCENTAGE of achievable points (never a raw/fixed-max score) ->
//     a band, with the two Step 2.1 hard gates capping the band independent
//     of points.
// NOT in scope here:
//   - Rendering (no Appendix D, no docx output — that's generate-prd.js in
//     Changeset 3B).
//   - Conflict detection (`⚠ Conflict` — that's Changeset 3C).
//   - Persisting the captured score into a rendered document (3B consumes
//     prd-content.js's `preDraftScorecard` field; this file only produces the
//     value that gets put there).
// ─────────────────────────────────────────────────────────────────────────────

// The six scored rubric categories, using the EXACT SKILL.md rubric section
// names — never paraphrase these. SKILL.md's "Completeness rubric" table and
// this config must name categories identically so a reader can line them up.
const CATEGORIES = [
  "1.1 Problem Statement",
  "1.3 KPIs",
  "2.1 Personas",
  "3.2 Functional Requirements",
  "6.1 Milestones",
  "6.2 Stakeholders",
];

// ── Per-category "bar" documentation (§C.1) ──────────────────────────────────
// The scorecard is a STRICT SUPERSET of the existing SKILL.md completeness
// rubric: the rubric checks presence; the scorecard checks presence PLUS
// specificity/quality. Documented once per category here (looked up by a
// statement's `category` field below) rather than repeated on every
// statement, so there is exactly one place to update a bar when it changes —
// duplicating this text across 2-3 statements per category would let copies
// drift silently, which is the exact failure mode this config exists to
// prevent (see docs/scorecard-proposal.md §D).
const CATEGORY_BARS = {
  "1.1 Problem Statement": {
    completenessRubricFloor: "Role, frequency, and cost of inaction named.",
    scorecardBar: "Same bar as the completeness rubric, split across two statements (role+frequency named; cost of inaction described) so each half can be scored independently.",
  },
  "1.3 KPIs": {
    completenessRubricFloor: "At least one metric with baseline, target, AND timeframe.",
    scorecardBar: "Now matches the completeness rubric's full 3-part bar exactly (metric+target, baseline, timeframe) as three separate statements. Earlier scorecard drafts omitted the timeframe statement — fixed per §C.2. This bar is not stricter than the rubric, it was previously incomplete and is now aligned.",
  },
  "2.1 Personas": {
    completenessRubricFloor: "Primary persona identified per the persona-definition rule.",
    scorecardBar: "Stricter than the rubric: also requires the persona's goal or pain point be explicitly stated, not just a name/label.",
  },
  "3.2 Functional Requirements": {
    completenessRubricFloor: "Every requirement has an assigned MoSCoW priority.",
    scorecardBar: "Stricter than the rubric: also requires requirements to describe testable behavior, not vague qualities like \"fast\" or \"easy\".",
  },
  "6.1 Milestones": {
    completenessRubricFloor: "At least one milestone with a date or explicit relative timeframe.",
    scorecardBar: "Stricter than the rubric: also probes whether Engineering/Design feasibility input exists for that timeframe, not just whether a date was stated.",
  },
  "6.2 Stakeholders": {
    completenessRubricFloor: "Named author plus sign-off status for each stakeholder.",
    scorecardBar: "Same bar as the completeness rubric: a named author (see HARD_GATE_FIELDS below — this is also a Step 2.1 hard gate) plus a known sign-off chain.",
  },
};

// ── The 13 scored statements (v1, confirmed 2026-07-22 — §C.3) ──────────────
// Each entry: id, category (exact rubric name, must exist in CATEGORIES),
// statement text, three anchor descriptions (what "Absent"/"Vague"/"Specific"
// looks like for THIS statement), and a weight (achievable points for this
// statement = weight * 2, since Specific = 2 points).
//
// The statement COUNT is not load-bearing anywhere in the scoring math below
// — scoreIntake() computes achievable points by summing this array, so
// adding, removing, or reweighting a statement reweights the bands
// automatically. Do not hardcode "13" (or any count) elsewhere.
const STATEMENTS = [
  {
    id: 1,
    category: "1.1 Problem Statement",
    statement: "Affected role and frequency are named",
    anchors: { absent: "Not mentioned", vague: "One of role/frequency, not both", specific: "Both named" },
    weight: 1,
  },
  {
    id: 2,
    category: "1.1 Problem Statement",
    statement: "Cost of inaction is described",
    anchors: { absent: "Not discussed", vague: "Gestured at", specific: "Quantified or concretely described" },
    weight: 1,
  },
  {
    id: 3,
    category: "1.3 KPIs",
    statement: "A target metric is named",
    anchors: { absent: "No metrics", vague: "Metric named, no target", specific: "Metric + target named" },
    weight: 1,
  },
  {
    id: 4,
    category: "1.3 KPIs",
    statement: "A baseline exists for that metric",
    anchors: { absent: "No baseline", vague: "Implied, not stated", specific: "Baseline stated" },
    weight: 1,
  },
  {
    id: 5,
    category: "1.3 KPIs",
    statement: "A timeframe is stated for the metric",
    anchors: { absent: "No timeframe", vague: "Vague (\"soon\")", specific: "Specific timeframe stated" },
    weight: 1,
    // Added per §C.2 — the original scorecard draft checked metric+target and
    // baseline but missed timeframe, even though the completeness rubric
    // (SKILL.md) always required all three. This statement closes that gap;
    // it's what makes the v1 set 13 statements instead of 12.
  },
  {
    id: 6,
    category: "2.1 Personas",
    statement: "End-user persona is identifiable, distinct from the author",
    anchors: { absent: "Undefined, or author = persona", vague: "Gestured at, thin", specific: "Named, distinct from author" },
    weight: 1,
  },
  {
    id: 7,
    category: "2.1 Personas",
    statement: "Persona's goal or pain point is stated",
    anchors: { absent: "Not discussed", vague: "Implied only", specific: "Explicitly stated" },
    weight: 1,
  },
  {
    id: 8,
    category: "3.2 Functional Requirements",
    statement: "Requirements describe behavior, not vague qualities",
    anchors: { absent: "UI-only or \"fast\"/\"easy\"", vague: "Some specific, some vague", specific: "Consistently specific/testable" },
    weight: 1,
  },
  {
    id: 9,
    category: "3.2 Functional Requirements",
    statement: "Requirements carry a priority signal",
    anchors: { absent: "None", vague: "Implied, not explicit", specific: "MoSCoW (or equivalent) explicit" },
    weight: 1,
  },
  {
    id: 10,
    category: "6.1 Milestones",
    statement: "A launch timeframe exists",
    anchors: { absent: "Not discussed", vague: "Vague", specific: "Specific date/quarter/unambiguous relative timeframe" },
    weight: 1,
  },
  {
    id: 11,
    category: "6.1 Milestones",
    statement: "Engineering/Design feasibility input exists",
    anchors: { absent: "None", vague: "Informal/partial", specific: "Explicitly discussed" },
    weight: 1,
  },
  {
    id: 12,
    category: "6.2 Stakeholders",
    statement: "A named author/owner exists",
    anchors: {
      absent: "Absent",
      // This statement is effectively binary in practice (there is rarely a
      // partial "author" state) — the table in docs/scorecard-proposal.md
      // §C.3 marks its Vague anchor "—" for the same reason. Documented as an
      // explicit N/A rather than left blank so it's clear this was a
      // deliberate reading of the source table, not an oversight.
      vague: "N/A — this statement has no meaningful partial state; score 1 only if a role/team is named without a specific person",
      specific: "Named",
    },
    weight: 1,
    // See HARD_GATE_FIELDS below: this statement is still scored 0/1/2 for
    // the 6.2 Stakeholders category subtotal like any other, but it is ALSO
    // one of the two Step 2.1 hard gates. The hard-gate PASS/FAIL check itself
    // is driven independently by scoreIntake()'s `hardGates` argument (which
    // reflects whatever Step 2.1 actually resolved), not by re-deriving gate
    // status from this statement's level — see the comment on
    // HARD_GATE_FIELDS for why.
    hardGateField: "authorNamed",
  },
  {
    id: 13,
    category: "6.2 Stakeholders",
    statement: "Sign-off chain is known",
    anchors: { absent: "Not discussed", vague: "Partial", specific: "Full chain named" },
    weight: 1,
  },
];

// ── Hard gates (§C.4, SKILL.md Step 2.1) ─────────────────────────────────────
// Two fields are required before ANY drafting starts (SKILL.md Step 2.1): a
// named author, and a usable problem statement. Per §C.4: "the band cannot
// read better than Not Enough to Start regardless of points" if either is
// absent — this check is independent of the 13 statements' point totals, a
// PRD could otherwise score well across every other statement and still ship
// without a named author.
//
// Why independent of the statement scores rather than derived from them:
// Step 2.1 already establishes (or asks for) these two fields BEFORE Step 2.2
// scoring runs at all. scoreIntake() re-checks whether that Step 2.1
// resolution actually landed (via the caller-supplied `hardGates` argument),
// rather than inferring gate status by re-reading statement #12's level or
// statement #1/#2's problem-statement levels. There is no dedicated
// "problem statement exists at all" statement among the 13 (statements #1/#2
// score its role/frequency/cost *specificity*, which presupposes one
// exists) — the hard gate check covers bare existence, the statements cover
// quality on top of that.
const HARD_GATE_FIELDS = ["authorNamed", "problemStatementUsable"];

// ── Bands (§C.4) ──────────────────────────────────────────────────────────
// Computed as a PERCENTAGE of achievable points, not a fixed max, so adding,
// removing, or reweighting a statement reweights the bands automatically —
// no rebasing needed. Ordered highest-first; bandForPercent() below walks
// this list and returns the first band whose minPercent the score clears.
const BANDS = [
  { name: "Draft-Ready", minPercent: 80 },
  { name: "Draftable, With Gaps", minPercent: 50 },
  { name: "Not Enough to Start", minPercent: 0 },
];

// ── Arithmetic ────────────────────────────────────────────────────────────

// Achievable points per statement = weight * 2 (max level is "Specific" = 2).
// Summed at call time, never hardcoded, so the statement set can grow/shrink
// freely (see the note on STATEMENTS above).
function achievablePoints(statement) {
  return (statement.weight || 1) * 2;
}

// Returns the band name for a raw percentage (0-100), ignoring hard gates.
// Exposed separately from scoreIntake() so callers/tests can check the
// percent-only banding in isolation from the hard-gate cap.
function bandForPercent(percent) {
  const band = BANDS.find(b => percent >= b.minPercent);
  return band ? band.name : BANDS[BANDS.length - 1].name;
}

// scoreIntake({ statementScores, hardGates }) -> result
//
//   statementScores: { [statementId]: 0 | 1 | 2 } — MUST have an entry for
//     every id in STATEMENTS. There is no "not yet assessed" state; if the
//     source/answers so far don't cover a statement, that's an Absent (0),
//     not a missing key. This is intentional — Step 2.2 scores "the
//     information gathered so far," and silence on a topic IS the Absent
//     signal, not a reason to skip scoring it.
//   hardGates: { authorNamed: boolean, problemStatementUsable: boolean } —
//     the outcome of Step 2.1, established BEFORE this function is called.
//
// Returns:
//   {
//     categories: {
//       [categoryName]: { earned, achievable, percent, statements: [...] }
//     },
//     totalEarned, totalAchievable, percent,   // percent = 0-100, rounded
//     percentBand,                              // band from percent alone
//     hardGateFailures: string[],               // subset of HARD_GATE_FIELDS
//     band,                                     // final, hard-gate-capped band
//   }
function scoreIntake({ statementScores, hardGates }) {
  if (!statementScores || typeof statementScores !== "object") {
    throw new Error("scoreIntake: statementScores object is required");
  }
  if (!hardGates || typeof hardGates !== "object") {
    throw new Error("scoreIntake: hardGates object is required (from Step 2.1)");
  }
  const missingGateFields = HARD_GATE_FIELDS.filter(f => typeof hardGates[f] !== "boolean");
  if (missingGateFields.length) {
    throw new Error(`scoreIntake: hardGates missing boolean field(s): ${missingGateFields.join(", ")}`);
  }

  const missingStatements = STATEMENTS.filter(s => !(s.id in statementScores));
  if (missingStatements.length) {
    throw new Error(`scoreIntake: missing score for statement id(s): ${missingStatements.map(s => s.id).join(", ")}`);
  }
  const invalidStatements = STATEMENTS.filter(s => ![0, 1, 2].includes(statementScores[s.id]));
  if (invalidStatements.length) {
    throw new Error(`scoreIntake: invalid score (must be 0, 1, or 2) for statement id(s): ${invalidStatements.map(s => s.id).join(", ")}`);
  }

  const categories = {};
  for (const categoryName of CATEGORIES) {
    categories[categoryName] = { earned: 0, achievable: 0, percent: 0, statements: [] };
  }

  let totalEarned = 0;
  let totalAchievable = 0;

  for (const s of STATEMENTS) {
    const level = statementScores[s.id];
    const earned = level * (s.weight || 1);
    const achievable = achievablePoints(s);
    totalEarned += earned;
    totalAchievable += achievable;

    const cat = categories[s.category];
    cat.earned += earned;
    cat.achievable += achievable;
    cat.statements.push({
      id: s.id,
      statement: s.statement,
      level,
      anchorText: level === 0 ? s.anchors.absent : level === 1 ? s.anchors.vague : s.anchors.specific,
    });
  }

  for (const categoryName of CATEGORIES) {
    const cat = categories[categoryName];
    cat.percent = cat.achievable ? Math.round((cat.earned / cat.achievable) * 100) : 0;
  }

  const percent = totalAchievable ? Math.round((totalEarned / totalAchievable) * 100) : 0;
  const percentBand = bandForPercent(percent);

  const hardGateFailures = HARD_GATE_FIELDS.filter(f => !hardGates[f]);
  const band = hardGateFailures.length ? "Not Enough to Start" : percentBand;

  return {
    categories,
    totalEarned,
    totalAchievable,
    percent,
    percentBand,
    hardGateFailures,
    band,
  };
}

module.exports = {
  CATEGORIES,
  CATEGORY_BARS,
  STATEMENTS,
  HARD_GATE_FIELDS,
  BANDS,
  bandForPercent,
  scoreIntake,
};
