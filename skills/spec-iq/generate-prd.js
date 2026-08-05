// ─────────────────────────────────────────────────────────────────────────────
// PRD STRUCTURE — this file is fixed rendering code, shared by every PRD this
// skill produces. To personalize a PRD, edit prd-content.js instead — never
// edit the section order, headers, table layout, or wording in this file.
// That separation is what keeps two independently-generated PRDs from the
// same input structurally identical, even when different people (or
// different sessions) fill in the content.
// ─────────────────────────────────────────────────────────────────────────────
const {
  Document, Packer, Paragraph, TextRun, Table, TableRow, TableCell,
  HeadingLevel, AlignmentType, BorderStyle, WidthType, ShadingType,
  LevelFormat, Footer, Header, TabStopType, PageNumberElement,
  PositionalTab, PositionalTabAlignment, PositionalTabRelativeTo, PositionalTabLeader
} = require('docx');
const fs = require('fs');
const CONTENT = require('./prd-content.js');
const SC = require('./scorecard-config.js');

// ─── Color palette ───────────────────────────────────────────────────────────
const BLUE      = "1F4E79";   // dark navy  (headings, accents)
const BLUE_MID  = "2E75B6";   // medium blue (H2, borders)
const BLUE_LITE = "D6E4F0";   // light blue  (header fills)
const GREY_LITE = "F2F2F2";   // light grey  (alternate fills)
const ORANGE    = "C55A11";   // guidance / gap-flag text color
const CONFLICT_RED = "C00000"; // conflict-flag text color (Changeset 3C) — distinct from ORANGE
const BLACK     = "000000";
const WHITE     = "FFFFFF";
const NONE      = "FFFFFF";

// ─── Border helpers ───────────────────────────────────────────────────────────
const cellBorder = (color = "CCCCCC") => ({
  top:    { style: BorderStyle.SINGLE, size: 1, color },
  bottom: { style: BorderStyle.SINGLE, size: 1, color },
  left:   { style: BorderStyle.SINGLE, size: 1, color },
  right:  { style: BorderStyle.SINGLE, size: 1, color },
});
const noBorder = () => ({
  top:    { style: BorderStyle.NONE, size: 0, color: NONE },
  bottom: { style: BorderStyle.NONE, size: 0, color: NONE },
  left:   { style: BorderStyle.NONE, size: 0, color: NONE },
  right:  { style: BorderStyle.NONE, size: 0, color: NONE },
});

// ─── Paragraph helpers ────────────────────────────────────────────────────────
const spacer = (pts = 6) => new Paragraph({
  children: [new TextRun("")],
  spacing: { before: 0, after: pts * 20 },
});

// Guidance = instructions ABOUT the section (structural, same every time).
const guidance = (text) => new Paragraph({
  children: [new TextRun({ text: `✏  ${text}`, color: ORANGE, italics: true, size: 20 })],
  spacing: { before: 60, after: 60 },
});

// Gap flag = a specific unresolved item for THIS PRD (content-driven).
// Same visual treatment as guidance (orange, flagged) but semantically it's
// "this wasn't in the source," not "here's how to fill this in."
const gapFlag = (text) => new Paragraph({
  children: [new TextRun({ text: `⚑  Gap: ${text}`, color: ORANGE, italics: true, size: 20 })],
  spacing: { before: 60, after: 60 },
});
const renderGaps = (gaps) => (gaps && gaps.length ? gaps.map(gapFlag) : []);

// ─── Conflict flag (Changeset 3C) ─────────────────────────────────────────────
// Conflict flag = CONTRADICTORY information found in the source for THIS PRD
// (two different values for the same thing), as opposed to a gap (MISSING
// information). Same paragraph shape as a gap flag, but a distinct color so
// the two are visually separable — see docs/scorecard-proposal.md §E.
const conflictFlag = (text) => new Paragraph({
  children: [new TextRun({ text: `⚠  Conflict: ${text}`, color: CONFLICT_RED, italics: true, size: 20 })],
  spacing: { before: 60, after: 60 },
});
const renderConflicts = (conflicts) => (conflicts && conflicts.length ? conflicts.map(conflictFlag) : []);

const bodyText = (text, opts = {}) => new Paragraph({
  children: [new TextRun({ text, size: 22, color: BLACK, ...opts })],
  spacing: { before: 60, after: 60 },
});

const divider = () => new Paragraph({
  children: [new TextRun("")],
  border: { bottom: { style: BorderStyle.SINGLE, size: 6, color: BLUE_MID, space: 1 } },
  spacing: { before: 120, after: 120 },
});

// ─── Table helpers ────────────────────────────────────────────────────────────
const headerCell = (text, width) => new TableCell({
  width: { size: width, type: WidthType.DXA },
  borders: cellBorder("AAAAAA"),
  shading: { fill: BLUE, type: ShadingType.CLEAR },
  margins: { top: 80, bottom: 80, left: 120, right: 120 },
  children: [new Paragraph({
    children: [new TextRun({ text, bold: true, color: WHITE, size: 20 })],
  })],
});

const dataCell = (text, width, fill = NONE, color = BLACK, italic = false) => new TableCell({
  width: { size: width, type: WidthType.DXA },
  borders: cellBorder("CCCCCC"),
  shading: { fill, type: ShadingType.CLEAR },
  margins: { top: 80, bottom: 80, left: 120, right: 120 },
  children: [new Paragraph({
    children: [new TextRun({ text, size: 20, color, italics: italic })],
  })],
});

const guidanceCell = (text, width) => new TableCell({
  width: { size: width, type: WidthType.DXA },
  borders: cellBorder("CCCCCC"),
  shading: { fill: "FFF8F0", type: ShadingType.CLEAR },
  margins: { top: 80, bottom: 80, left: 120, right: 120 },
  children: [new Paragraph({
    children: [new TextRun({ text: `✏  ${text}`, size: 20, color: ORANGE, italics: true })],
  })],
});

// ─── Numbered-list helper ───────────────────────────────────────────────────
// Every discrete list of structured content in this document renders as a
// numbered list, not a bulleted one — each call site passes its own
// `ref` so its numbering restarts at 1 independently of every other list.
const numberedItem = (text, ref, opts = {}) => new Paragraph({
  numbering: { reference: ref, level: 0 },
  children: [new TextRun({ text, size: 22, ...opts })],
  spacing: { before: 40, after: 40 },
});

// ─── Section title ─────────────────────────────────────────────────────────────
const sectionTitle = (text) => new Paragraph({
  heading: HeadingLevel.HEADING_1,
  children: [new TextRun({ text, color: WHITE, size: 28, bold: true })],
  shading: { fill: BLUE, type: ShadingType.CLEAR },
  spacing: { before: 280, after: 120 },
});

const subTitle = (text) => new Paragraph({
  heading: HeadingLevel.HEADING_2,
  children: [new TextRun({ text, color: BLUE, size: 24, bold: true })],
  spacing: { before: 180, after: 80 },
  border: { bottom: { style: BorderStyle.SINGLE, size: 4, color: BLUE_MID, space: 1 } },
});

// ─── MoSCoW table (fixed framework — never customized per-PRD) ────────────────
const moscowTable = () => {
  const cols = [2000, 3200, 4160];
  const total = cols.reduce((a, b) => a + b, 0); // 9360
  const rows = [
    ["Must Have",    "M", "Critical — launch is blocked without this"],
    ["Should Have",  "S", "High value — include if time permits"],
    ["Could Have",   "C", "Nice-to-have — defer to later release"],
    ["Won't Have",   "W", "Explicitly out of scope for this release"],
  ];
  const fills = [BLUE_LITE, "D4EDDA", GREY_LITE, "FFF3CD"];
  return new Table({
    width: { size: total, type: WidthType.DXA },
    columnWidths: cols,
    rows: [
      new TableRow({ children: [headerCell("Priority", cols[0]), headerCell("Code", cols[1]), headerCell("Meaning", cols[2])] }),
      ...rows.map((r, i) => new TableRow({
        children: [
          dataCell(r[0], cols[0], fills[i], BLACK, false),
          dataCell(r[1], cols[1], fills[i], BLUE, true),
          dataCell(r[2], cols[2], fills[i]),
        ],
      })),
    ],
  });
};

// ─── Requirements table ───────────────────────────────────────────────────────
const requirementsTable = () => {
  const cols = [720, 2000, 3640, 1600, 1400];
  const total = cols.reduce((a, b) => a + b, 0);
  const priorityFill = (p) => p === "M" ? BLUE_LITE : p === "S" ? "D4EDDA" : p === "C" ? GREY_LITE : "FFF3CD";
  return new Table({
    width: { size: total, type: WidthType.DXA },
    columnWidths: cols,
    rows: [
      new TableRow({ children: ["#", "Category", "Requirement", "Priority", "Notes"].map((h, i) => headerCell(h, cols[i])) }),
      ...CONTENT.requirementRows.map(r => new TableRow({ children: [
        dataCell(r[0], cols[0], GREY_LITE),
        dataCell(r[1], cols[1]),
        dataCell(r[2], cols[2]),
        dataCell(r[3], cols[3], priorityFill(r[3]), BLUE),
        dataCell(r[4], cols[4]),
      ]})),
      new TableRow({ children: [
        guidanceCell("...", cols[0]),
        guidanceCell("Add rows for each requirement", cols[1]),
        guidanceCell("Be specific — avoid vague language like 'fast' or 'easy'", cols[2]),
        guidanceCell("M/S/C/W", cols[3], "FFF8F0"),
        dataCell("", cols[4]),
      ]}),
    ],
  });
};

// ─── Non-functional requirements table ────────────────────────────────────────
const nfrTable = () => {
  const cols = [500, 1900, 4260, 1400, 1200];
  return new Table({
    width: { size: 9260, type: WidthType.DXA },
    columnWidths: cols,
    rows: [
      new TableRow({ children: ["#", "Category", "Requirement", "Priority", "Metric"].map((h, i) => headerCell(h, cols[i])) }),
      ...CONTENT.nfrRows.map((r, i) => new TableRow({ children: [
        dataCell(String(i + 1), cols[0], GREY_LITE),
        dataCell(r[0], cols[1], i % 2 === 0 ? GREY_LITE : NONE),
        dataCell(r[1], cols[2]),
        dataCell(r[2], cols[3], r[2] === "M" ? BLUE_LITE : "D4EDDA", BLUE),
        dataCell(r[3], cols[4]),
      ]})),
    ],
  });
};

// ─── Decisions log table ──────────────────────────────────────────────────────
const decisionsTable = () => {
  const cols = [500, 1600, 2200, 2500, 2560];
  const total = cols.reduce((a, b) => a + b, 0);
  return new Table({
    width: { size: total, type: WidthType.DXA },
    columnWidths: cols,
    rows: [
      new TableRow({ children: ["#", "Date", "Decision", "Rationale", "Owner"].map((h, i) => headerCell(h, cols[i])) }),
      ...CONTENT.decisionRows.map((r, i) => new TableRow({ children: [
        dataCell(String(i + 1), cols[0], GREY_LITE),
        dataCell(r[0], cols[1], GREY_LITE),
        dataCell(r[1], cols[2]),
        dataCell(r[2], cols[3]),
        dataCell(r[3], cols[4]),
      ]})),
      new TableRow({ children: [
        guidanceCell("...", cols[0]),
        guidanceCell("Use ISO 8601 (YYYY-MM-DD)", cols[1]),
        guidanceCell("State what was decided, not just discussed", cols[2]),
        guidanceCell("Include alternatives considered", cols[3]),
        guidanceCell("Person accountable", cols[4]),
      ]}),
    ],
  });
};

// ─── Open questions table ─────────────────────────────────────────────────────
const questionsTable = () => {
  const cols = [720, 3640, 2000, 1800, 1200];
  const total = cols.reduce((a, b) => a + b, 0);
  const statusFill = (s) => /open/i.test(s) ? "FFF3CD" : /parked/i.test(s) ? "F2F2F2" : NONE;
  return new Table({
    width: { size: total, type: WidthType.DXA },
    columnWidths: cols,
    rows: [
      new TableRow({ children: ["#", "Question", "Owner", "Due", "Status"].map((h, i) => headerCell(h, cols[i])) }),
      ...CONTENT.questionRows.map(r => new TableRow({ children: [
        dataCell(r[0], cols[0], GREY_LITE),
        dataCell(r[1], cols[1]),
        dataCell(r[2], cols[2]),
        dataCell(r[3], cols[3]),
        dataCell(r[4], cols[4], statusFill(r[4])),
      ]})),
    ],
  });
};

// ─── Stakeholder table ────────────────────────────────────────────────────────
const stakeholderTable = () => {
  const cols = [500, 2000, 2200, 2360, 2200];
  const total = cols.reduce((a, b) => a + b, 0);
  const signOffFill = (s) => /yes/i.test(s) ? "D4EDDA" : /informed/i.test(s) ? "FFF3CD" : GREY_LITE;
  return new Table({
    width: { size: total, type: WidthType.DXA },
    columnWidths: cols,
    rows: [
      new TableRow({ children: ["#", "Name", "Role", "Responsibilities", "Sign-off Required?"].map((h, i) => headerCell(h, cols[i])) }),
      ...CONTENT.stakeholderRows.map((r, i) => new TableRow({ children: [
        dataCell(String(i + 1), cols[0], GREY_LITE),
        dataCell(r[0], cols[1]),
        dataCell(r[1], cols[2]),
        dataCell(r[2], cols[3]),
        dataCell(r[3], cols[4], signOffFill(r[3])),
      ]})),
      new TableRow({ children: [
        guidanceCell("...", cols[0]),
        dataCell("TBD", cols[1], GREY_LITE),
        guidanceCell("Add all key stakeholders", cols[2]),
        guidanceCell("Who does what?", cols[3]),
        guidanceCell("Yes / No / Informed", cols[4]),
      ]}),
    ],
  });
};

// ─── Milestones table ─────────────────────────────────────────────────────────
const milestonesTable = () => {
  const cols = [500, 2300, 2800, 2160, 1600];
  const total = cols.reduce((a, b) => a + b, 0);
  return new Table({
    width: { size: total, type: WidthType.DXA },
    columnWidths: cols,
    rows: [
      new TableRow({ children: ["#", "Milestone", "Deliverable", "Date", "Owner"].map((h, i) => headerCell(h, cols[i])) }),
      ...CONTENT.milestoneRows.map((r, i) => new TableRow({ children: [
        dataCell(String(i + 1), cols[0], GREY_LITE),
        dataCell(r[0], cols[1]),
        dataCell(r[1], cols[2]),
        dataCell(r[2], cols[3], GREY_LITE),
        dataCell(r[3], cols[4]),
      ]})),
    ],
  });
};

// ─── Cover box ────────────────────────────────────────────────────────────────
const coverInfoTable = () => {
  const cols = [2400, 6960];
  const total = cols.reduce((a, b) => a + b, 0);
  const row = (label, valueText, isGuidance = false) => new TableRow({
    children: [
      new TableCell({
        width: { size: cols[0], type: WidthType.DXA },
        borders: cellBorder("AAAAAA"),
        shading: { fill: BLUE, type: ShadingType.CLEAR },
        margins: { top: 80, bottom: 80, left: 120, right: 120 },
        children: [new Paragraph({ children: [new TextRun({ text: label, bold: true, color: WHITE, size: 20 })] })],
      }),
      new TableCell({
        width: { size: cols[1], type: WidthType.DXA },
        borders: cellBorder("CCCCCC"),
        shading: { fill: isGuidance ? "FFF8F0" : NONE, type: ShadingType.CLEAR },
        margins: { top: 80, bottom: 80, left: 120, right: 120 },
        children: [new Paragraph({
          children: [new TextRun({
            text: isGuidance ? `✏  ${valueText}` : valueText,
            size: 20,
            color: isGuidance ? ORANGE : BLACK,
            italics: isGuidance,
          })],
        })],
      }),
    ],
  });
  const c = CONTENT.cover;
  return new Table({
    width: { size: total, type: WidthType.DXA },
    columnWidths: cols,
    rows: [
      row("Product Name", c.productName),
      row("Version", c.version, false),
      row("Status", c.status, !!c.statusIsGuidance),
      row("Author(s)", c.authors),
      row("Last Updated", c.lastUpdated),
      row("Target Launch", c.targetLaunch),
    ],
  });
};

// ─── KPIs table ───────────────────────────────────────────────────────────────
const kpiTable = () => {
  const cols = [500, 2700, 2400, 2160, 1600];
  const total = cols.reduce((a, b) => a + b, 0);
  return new Table({
    width: { size: total, type: WidthType.DXA },
    columnWidths: cols,
    rows: [
      new TableRow({ children: ["#", "Metric", "Baseline", "Target", "Timeframe"].map((h, i) => headerCell(h, cols[i])) }),
      ...CONTENT.kpiRows.map((r, i) => new TableRow({ children: [
        dataCell(String(i + 1), cols[0], GREY_LITE),
        dataCell(r[0], cols[1]),
        dataCell(r[1], cols[2], GREY_LITE),
        dataCell(r[2], cols[3], "D4EDDA"),
        dataCell(r[3], cols[4]),
      ]})),
      new TableRow({ children: [
        guidanceCell("...", cols[0]),
        guidanceCell("Add the metrics that will tell you if this shipped successfully", cols[1]),
        guidanceCell("Current state", cols[2]),
        guidanceCell("Specific, time-bound target", cols[3]),
        guidanceCell("When to measure", cols[4]),
      ]}),
    ],
  });
};

// ─── User story table ─────────────────────────────────────────────────────────
const userStoryTable = () => {
  const cols = [500, 1400, 4060, 3400];
  const total = cols.reduce((a, b) => a + b, 0);
  return new Table({
    width: { size: total, type: WidthType.DXA },
    columnWidths: cols,
    rows: [
      new TableRow({ children: ["#", "Persona", "User Story", "Acceptance Criteria"].map((h, i) => headerCell(h, cols[i])) }),
      ...CONTENT.userStoryRows.map((r, i) => new TableRow({ children: [
        dataCell(String(i + 1), cols[0], GREY_LITE),
        dataCell(r[0], cols[1]),
        dataCell(r[1], cols[2]),
        dataCell(r[2], cols[3]),
      ]})),
      new TableRow({ children: [
        guidanceCell("...", cols[0]),
        guidanceCell("Who?", cols[1]),
        guidanceCell("As a [persona], I want to [action] so that [outcome]", cols[2]),
        guidanceCell("The 'done' criteria that QA will test against", cols[3]),
      ]}),
    ],
  });
};

// ─── Current workflow table ───────────────────────────────────────────────────
const currentWorkflowTable = () => {
  const cols = [500, 4430, 4430];
  return new Table({
    width: { size: cols.reduce((a, b) => a + b, 0), type: WidthType.DXA },
    columnWidths: cols,
    rows: [
      new TableRow({ children: [headerCell("#", cols[0]), headerCell("Current State (Pain)", cols[1]), headerCell("Desired Future State", cols[2])] }),
      ...CONTENT.currentWorkflowRows.map((r, i) => new TableRow({ children: [
        dataCell(String(i + 1), cols[0], GREY_LITE),
        dataCell(r[0], cols[1]),
        dataCell(r[1], cols[2], "D4EDDA"),
      ]})),
    ],
  });
};

// ─── Edge cases table ─────────────────────────────────────────────────────────
const edgeCaseTable = () => {
  const cols = [500, 3000, 3000, 2860];
  return new Table({
    width: { size: cols.reduce((a, b) => a + b, 0), type: WidthType.DXA },
    columnWidths: cols,
    rows: [
      new TableRow({ children: ["#", "Scenario", "Expected Behavior", "User Message"].map((h, i) => headerCell(h, cols[i])) }),
      ...CONTENT.edgeCaseRows.map((r, i) => new TableRow({ children: [
        dataCell(String(i + 1), cols[0], GREY_LITE),
        dataCell(r[0], cols[1]),
        dataCell(r[1], cols[2]),
        dataCell(r[2], cols[3]),
      ]})),
      new TableRow({ children: [
        guidanceCell("...", cols[0]),
        guidanceCell("Add all known edge cases here", cols[1]),
        guidanceCell("What does the system do?", cols[2]),
        guidanceCell("Exact copy for the UI message", cols[3]),
      ]}),
    ],
  });
};

// ─── Constraints & dependencies table ─────────────────────────────────────────
const constraintsTable = () => {
  const cols = [500, 2200, 2200, 4460];
  return new Table({
    width: { size: cols.reduce((a, b) => a + b, 0), type: WidthType.DXA },
    columnWidths: cols,
    rows: [
      new TableRow({ children: ["#", "Type", "Item", "Details"].map((h, i) => headerCell(h, cols[i])) }),
      ...CONTENT.constraintsRows.map((r, i) => new TableRow({ children: [
        dataCell(String(i + 1), cols[0], GREY_LITE),
        dataCell(r[0], cols[1], GREY_LITE),
        dataCell(r[1], cols[2]),
        dataCell(r[2], cols[3]),
      ]})),
      new TableRow({ children: [
        guidanceCell("...", cols[0]),
        guidanceCell("Platform / Integration / Dependency / Constraint", cols[1]),
        guidanceCell("Name the system or team", cols[2]),
        guidanceCell("Version, limits, contacts, blockers", cols[3]),
      ]}),
    ],
  });
};

// ─── Version history table ────────────────────────────────────────────────────
const versionHistoryTable = () => new Table({
  width: { size: 9360, type: WidthType.DXA },
  columnWidths: [1600, 1600, 3960, 2200],
  rows: [
    new TableRow({ children: ["Version", "Date", "Summary of Changes", "Author"].map((h, i) => headerCell(h, [1600,1600,3960,2200][i])) }),
    ...CONTENT.versionHistoryRows.map(r => new TableRow({ children: [
      dataCell(r[0], 1600, GREY_LITE),
      dataCell(r[1], 1600),
      dataCell(r[2], 3960),
      dataCell(r[3], 2200),
    ]})),
    new TableRow({ children: [
      guidanceCell("Increment on every significant change", 1600),
      guidanceCell("ISO 8601 (YYYY-MM-DD)", 1600),
      guidanceCell("What changed and why", 3960),
      guidanceCell("Who made the change", 2200),
    ]}),
  ],
});

// ─── Glossary table ────────────────────────────────────────────────────────────
const glossaryTable = () => new Table({
  width: { size: 9360, type: WidthType.DXA },
  columnWidths: [2400, 6960],
  rows: [
    new TableRow({ children: [headerCell("Term", 2400), headerCell("Definition", 6960)] }),
    ...CONTENT.glossaryRows.map((r, i) => new TableRow({ children: [
      dataCell(r[0], 2400, i % 2 === 0 ? GREY_LITE : NONE, BLACK, false),
      dataCell(r[1], 6960),
    ]})),
  ],
});

// ─── Appendix D: pre/post intake readiness scorecard (Changeset 3B) ──────────
// Pre-Draft column: read VERBATIM from CONTENT.preDraftScorecard — this is the
// Step 2.2 result captured during intake (see prd-content.js's field comment).
// Never recomputed here — see docs/scorecard-proposal.md §C.5.
//
// Post-Draft column: re-scored HERE, at render time, from this draft's actual
// `prd-content.js` content and `gaps` state (not the original source
// material). Each of the six scored categories gets a coarse 0/1/2
// (Absent/Vague/Specific) judgment — Absent if the section is still the
// shipped default (the same failure mode scripts/self-audit.js flags as
// leftover boilerplate), Vague if it's been filled in but a gap remains,
// Specific if filled in with no open gap — then that level is applied
// uniformly to every one of scorecard-config.js's 13 statements in that
// category and run through the SAME `scoreIntake()` used for the pre-draft
// score, so pre and post are guaranteed to band and percentage identically.
// This is deliberately coarser than the statement-level judgment a human (or
// Claude, during Step 2.2) makes from source text — there is no source text
// to re-read at render time, only the content that made it into the file.

// Mirrors the exact shipped defaults in prd-content.js (same spirit as
// scripts/self-audit.js's MARKERS list) so a still-default section reads as
// Absent here the same way self-audit flags it as unshipped boilerplate.
const DEFAULT_PROBLEM_STATEMENT_TEXT = "[Example] Account managers spend an average of 3 hours per week manually compiling client reports from three separate tools. This delays delivery, introduces errors, and reduces time available for strategic client work. As the client base scales past 500 accounts, this process is no longer sustainable.";
const DEFAULT_KPI_ROWS_JSON = JSON.stringify([
  ["Monthly Active Users (MAU)", "12,000", "20,000", "6 months"],
  ["Task completion rate", "62%", "80%", "3 months"],
]);
const DEFAULT_PRIMARY_PERSONA_LABEL = "Alex — Senior Account Manager";
const DEFAULT_SECONDARY_PERSONA_LABEL = "Jordan — Operations Manager";
const DEFAULT_REQUIREMENT_ROWS_JSON = JSON.stringify([
  ["1", "Authentication", "Users must be able to log in with email + password", "M", "Link to design specs"],
  ["2", "Performance", "Page load < 2s on 4G connection", "M", "Benchmark target"],
  ["3", "Accessibility", "WCAG 2.1 AA compliance", "S", "Audit tool TBD"],
]);
const DEFAULT_MILESTONE_ROWS_JSON = JSON.stringify([
  ["Discovery complete", "Signed-off PRD", "YYYY-MM-DD", "PM"],
  ["Design handoff", "Figma specs + component library", "YYYY-MM-DD", "Design Lead"],
  ["Engineering kickoff", "Sprint plan + story points", "YYYY-MM-DD", "Eng Lead"],
  ["Beta launch", "Feature-complete build", "YYYY-MM-DD", "PM"],
  ["GA launch", "Public release", "YYYY-MM-DD", "PM"],
]);
const DEFAULT_STAKEHOLDER_ROWS_JSON = JSON.stringify([
  ["Jane Smith", "Product Manager", "Author, final approval", "Yes"],
  ["Alex Johnson", "Engineering Lead", "Feasibility review", "Yes"],
]);
const DEFAULT_AUTHORS = "Name, Title";

// category name (exact SC.CATEGORIES entry) -> { isDefault(), gaps(), conflicts() }
// conflicts() added Changeset 3C — mirrors gaps() exactly, reading the sibling
// `conflicts`/`xConflicts` field added to prd-content.js alongside each gaps field.
const CATEGORY_POST_DRAFT_SOURCES = {
  "1.1 Problem Statement": {
    isDefault: () => CONTENT.problemStatement.text === DEFAULT_PROBLEM_STATEMENT_TEXT,
    gaps: () => CONTENT.problemStatement.gaps || [],
    conflicts: () => CONTENT.problemStatement.conflicts || [],
  },
  "1.3 KPIs": {
    isDefault: () => JSON.stringify(CONTENT.kpiRows) === DEFAULT_KPI_ROWS_JSON,
    gaps: () => CONTENT.kpiGaps || [],
    conflicts: () => CONTENT.kpiConflicts || [],
  },
  "2.1 Personas": {
    isDefault: () => CONTENT.personas.primary.label === DEFAULT_PRIMARY_PERSONA_LABEL
      && CONTENT.personas.secondary.label === DEFAULT_SECONDARY_PERSONA_LABEL,
    gaps: () => CONTENT.personas.gaps || [],
    conflicts: () => CONTENT.personas.conflicts || [],
  },
  "3.2 Functional Requirements": {
    isDefault: () => JSON.stringify(CONTENT.requirementRows) === DEFAULT_REQUIREMENT_ROWS_JSON,
    gaps: () => CONTENT.requirementGaps || [],
    conflicts: () => CONTENT.requirementConflicts || [],
  },
  "6.1 Milestones": {
    isDefault: () => JSON.stringify(CONTENT.milestoneRows) === DEFAULT_MILESTONE_ROWS_JSON,
    gaps: () => CONTENT.milestoneGaps || [],
    conflicts: () => CONTENT.milestoneConflicts || [],
  },
  "6.2 Stakeholders": {
    isDefault: () => JSON.stringify(CONTENT.stakeholderRows) === DEFAULT_STAKEHOLDER_ROWS_JSON,
    gaps: () => CONTENT.stakeholderGaps || [],
    conflicts: () => CONTENT.stakeholderConflicts || [],
  },
};

// 0 (Absent) / 1 (Vague) / 2 (Specific) per docs/scorecard-proposal.md §C.5.
// Changeset 3C: an unresolved conflict pulls a category down to level 1 the
// same way an open gap does — see docs/scorecard-proposal.md §E.
function postDraftCategoryLevel(categoryName) {
  const src = CATEGORY_POST_DRAFT_SOURCES[categoryName];
  if (src.isDefault()) return 0;
  return (src.gaps().length || src.conflicts().length) ? 1 : 2;
}

// Re-scores every category through scorecard-config.js's own scoreIntake(),
// never reimplementing the banding/percentage math here — see the "Do NOT
// change the pre-draft scoring logic" guardrail in the 3B changeset spec.
function scorePostDraft() {
  const statementScores = {};
  for (const s of SC.STATEMENTS) {
    statementScores[s.id] = postDraftCategoryLevel(s.category);
  }
  const hardGates = {
    authorNamed: !!CONTENT.cover.authors && CONTENT.cover.authors.trim() !== "" && CONTENT.cover.authors !== DEFAULT_AUTHORS,
    problemStatementUsable: !!CONTENT.problemStatement.text && CONTENT.problemStatement.text.trim() !== "" && CONTENT.problemStatement.text !== DEFAULT_PROBLEM_STATEMENT_TEXT,
  };
  return SC.scoreIntake({ statementScores, hardGates });
}

// A percent is Specific only at 100 and Absent only at 0 because every
// statement within a post-draft category shares one uniform level (see
// postDraftCategoryLevel above); applying the same rule to the pre-draft
// percent (which CAN land at odd in-between values, since 2.2 scores each
// statement independently) keeps both columns using one consistent label
// scale for display.
function tierLabel(percent) {
  return percent >= 100 ? "Specific" : percent <= 0 ? "Absent" : "Vague";
}

// ─── Post-Draft clarity fixes (Changeset 3C, docs/scorecard-clarity-proposal.md) ──
// Item 1: a SEPARATE label function for the post-draft column, forked off
// tierLabel() rather than editing it — tierLabel() is shared with the
// pre-draft column (see its call site below) and must stay untouched so the
// pre-draft column's wording can never drift from what Step 2.2 showed the
// user (Changeset 3B's verbatim guarantee). Conflict-aware: a level-1 result
// caused by an unresolved conflict must not read as a "gap."
function postDraftTierLabel(categoryName, level) {
  if (level === 0) return "Not Started";
  if (level === 2) return "Fully Resolved";
  const src = CATEGORY_POST_DRAFT_SOURCES[categoryName];
  const hasGap = src.gaps().length > 0;
  const hasConflict = src.conflicts().length > 0;
  if (hasGap && hasConflict) return "Gaps/Conflicts Remaining";
  if (hasConflict) return "Conflict Unresolved";
  return "Gaps Remaining";
}

// Item 2: only the level-1 branch is enriched (to name the actual open gap/
// conflict); the other three branches (default / no-baseline / resolved- /
// already-specific) keep their exact original order and logic. Keyed off the
// numeric `level` (0/1/2), not a label string, so it doesn't depend on
// postDraftTierLabel's exact wording. Conflicts are listed first (more
// urgent/actionable than a plain gap) when a category has both.
function deltaNote(categoryName, preLabel, level, openGapCount, openConflictCount) {
  if (level === 0) return "Still default — not customized";
  if (level === 1) {
    const src = CATEGORY_POST_DRAFT_SOURCES[categoryName];
    const parts = [];
    if (openConflictCount) parts.push(`${openConflictCount} conflict${openConflictCount > 1 ? "s" : ""} unresolved: "${src.conflicts()[0]}"`);
    if (openGapCount) parts.push(`${openGapCount} gap${openGapCount > 1 ? "s" : ""} remaining: "${src.gaps()[0]}"`);
    return `Still open — see ${categoryName}: ${parts.join("; ")}`;
  }
  if (preLabel === null) return "No pre-draft baseline captured";
  if (preLabel !== "Specific") return "Resolved during drafting";
  return "Already specific at intake";
}

const appendixDTable = () => {
  const cols = [2800, 1900, 1900, 2760];
  const total = cols.reduce((a, b) => a + b, 0); // 9360
  const pre = CONTENT.preDraftScorecard ? CONTENT.preDraftScorecard.result : null;
  const post = scorePostDraft();

  const categoryRows = SC.CATEGORIES.map(categoryName => {
    const postPercent = post.categories[categoryName].percent;
    // level computed once per row (Changeset 3C) and threaded into both the
    // label and the delta note — never re-derived from a label string.
    const level = postDraftCategoryLevel(categoryName);
    const postLabel = postDraftTierLabel(categoryName, level);
    const openGapCount = CATEGORY_POST_DRAFT_SOURCES[categoryName].gaps().length;
    const openConflictCount = CATEGORY_POST_DRAFT_SOURCES[categoryName].conflicts().length;
    // Pre-draft column: UNCHANGED from Changeset 3B — still tierLabel()-worded,
    // still read verbatim from the captured preDraftScorecard. Not touched here.
    const preLabel = pre ? tierLabel(pre.categories[categoryName].percent) : null;
    const preCellText = pre ? `${preLabel} (${pre.categories[categoryName].percent}%)` : "Not captured";
    return [
      categoryName,
      preCellText,
      `${postLabel} (${postPercent}%)`,
      deltaNote(categoryName, preLabel, level, openGapCount, openConflictCount),
    ];
  });

  const overallRow = [
    "Overall",
    pre ? `${pre.band} (${pre.percent}%)` : "Not captured",
    `${post.band} (${post.percent}%)`,
    "Advisory only — see SKILL.md Step 2.2",
  ];

  return new Table({
    width: { size: total, type: WidthType.DXA },
    columnWidths: cols,
    rows: [
      new TableRow({ children: ["Category", "Pre-Draft", "Post-Draft", "Notes"].map((h, i) => headerCell(h, cols[i])) }),
      ...categoryRows.map(r => new TableRow({ children: [
        dataCell(r[0], cols[0], GREY_LITE),
        dataCell(r[1], cols[1]),
        dataCell(r[2], cols[2]),
        dataCell(r[3], cols[3]),
      ]})),
      new TableRow({ children: [
        dataCell(overallRow[0], cols[0], BLUE_LITE, BLUE, true),
        dataCell(overallRow[1], cols[1], BLUE_LITE, BLUE, true),
        dataCell(overallRow[2], cols[2], BLUE_LITE, BLUE, true),
        dataCell(overallRow[3], cols[3], BLUE_LITE),
      ]}),
    ],
  });
};

// ─── Persona cards ────────────────────────────────────────────────────────────
const personaCard = (label, fill, p) => new TableCell({
  width: { size: 4680, type: WidthType.DXA },
  borders: cellBorder("AAAAAA"),
  shading: { fill, type: ShadingType.CLEAR },
  margins: { top: 100, bottom: 100, left: 140, right: 140 },
  children: [
    new Paragraph({ children: [new TextRun({ text: label, bold: true, size: 22, color: BLUE })], spacing: { after: 60 } }),
    new Paragraph({ children: [new TextRun({ text: p.label, bold: true, size: 20 })], spacing: { after: 40 } }),
    new Paragraph({ children: [new TextRun({ text: "Goal: ", bold: true, size: 20 }), new TextRun({ text: p.goal, size: 20 })], spacing: { after: 40 } }),
    new Paragraph({ children: [new TextRun({ text: "Pain: ", bold: true, size: 20 }), new TextRun({ text: p.pain, size: 20 })], spacing: { after: 40 } }),
    new Paragraph({ children: [new TextRun({ text: p.quote, size: 20, italics: true, color: "555555" })], spacing: { after: 40 } }),
    new Paragraph({ children: [new TextRun({ text: "Tech comfort: ", bold: true, size: 20 }), new TextRun({ text: p.techComfort, size: 20 })] }),
  ],
});

const personaTable = () => new Table({
  width: { size: 9360, type: WidthType.DXA },
  columnWidths: [4680, 4680],
  rows: [
    new TableRow({ children: [
      personaCard("👤  Primary Persona", BLUE_LITE, CONTENT.personas.primary),
      personaCard("👤  Secondary Persona", GREY_LITE, CONTENT.personas.secondary),
    ]}),
  ],
});

// ─── Document assembly ────────────────────────────────────────────────────────
const doc = new Document({
  styles: {
    default: { document: { run: { font: "Arial", size: 22 } } },
    paragraphStyles: [
      {
        id: "Heading1", name: "Heading 1", basedOn: "Normal", next: "Normal", quickFormat: true,
        run: { size: 28, bold: true, font: "Arial", color: WHITE },
        paragraph: { spacing: { before: 280, after: 120 }, outlineLevel: 0,
          shading: { fill: BLUE, type: ShadingType.CLEAR } },
      },
      {
        id: "Heading2", name: "Heading 2", basedOn: "Normal", next: "Normal", quickFormat: true,
        run: { size: 24, bold: true, font: "Arial", color: BLUE },
        paragraph: { spacing: { before: 180, after: 80 }, outlineLevel: 1 },
      },
    ],
  },
  numbering: {
    config: [
      // Each reference below restarts its own numbering at 1, independent of
      // every other list in the document — that's why each logical list gets
      // its own reference name rather than sharing one.
      ...[
        "business-objectives", "scope-in-scope", "scope-out-of-scope",
        "design-references", "data-privacy", "integration-points",
        "related-documents", "howto-list",
      ].map(ref => ({
        reference: ref,
        levels: [{ level: 0, format: LevelFormat.DECIMAL, text: "%1.", alignment: AlignmentType.LEFT,
          style: { paragraph: { indent: { left: 720, hanging: 360 } } } }],
      })),
      // One per user flow, so each flow's steps restart at 1.
      ...CONTENT.userFlows.map((_, i) => ({
        reference: `userflow-steps-${i}`,
        levels: [{ level: 0, format: LevelFormat.DECIMAL, text: "%1.", alignment: AlignmentType.LEFT,
          style: { paragraph: { indent: { left: 720, hanging: 360 } } } }],
      })),
    ],
  },
  sections: [{
    properties: {
      page: {
        size: { width: 12240, height: 15840 },
        margin: { top: 1080, right: 1080, bottom: 1080, left: 1080 },
      },
    },
    headers: {
      default: new Header({
        children: [
          new Paragraph({
            children: [
              new TextRun({ text: "PRODUCT REQUIREMENTS DOCUMENT", color: BLUE, bold: true, size: 18 }),
              new TextRun({ text: "\t", size: 18 }),
              new TextRun({ text: "CONFIDENTIAL · DRAFT", color: "999999", size: 16, italics: true }),
            ],
            tabStops: [{ type: TabStopType.RIGHT, position: 9000 }],
            border: { bottom: { style: BorderStyle.SINGLE, size: 6, color: BLUE_MID, space: 1 } },
            spacing: { after: 80 },
          }),
        ],
      }),
    },
    footers: {
      default: new Footer({
        children: [
          new Paragraph({
            children: [
              new TextRun({ text: "Page ", size: 18, color: "999999" }),
              new TextRun({ text: " · ", size: 18, color: "999999" }),
              new TextRun({ text: `\t${CONTENT.cover.footerProductLabel}`, size: 18, color: "999999", italics: true }),
            ],
            tabStops: [{ type: TabStopType.RIGHT, position: 9000 }],
            border: { top: { style: BorderStyle.SINGLE, size: 4, color: "CCCCCC", space: 1 } },
            spacing: { before: 80 },
          }),
        ],
      }),
    },
    children: [

      // ── COVER ──────────────────────────────────────────────────────────────
      new Paragraph({
        children: [new TextRun({ text: CONTENT.cover.docTitle, bold: true, size: 48, color: BLUE })],
        alignment: AlignmentType.CENTER,
        spacing: { before: 480, after: 240 },
      }),
      new Paragraph({
        children: [new TextRun({ text: CONTENT.cover.docSubtitle, size: 24, color: "555555", italics: true })],
        alignment: AlignmentType.CENTER,
        spacing: { after: 480 },
      }),
      coverInfoTable(),
      spacer(24),
      new Paragraph({
        children: [new TextRun({ text: "How to use this template", bold: true, size: 24, color: BLUE })],
        spacing: { before: 240, after: 120 },
      }),
      bodyText("This document is structured to take you from problem through to execution. Complete each section in order — the thinking required for earlier sections directly informs later ones. Guidance notes (shown in orange) explain what belongs in each field; delete them before sharing with stakeholders."),
      spacer(6),
      numberedItem("Orange italic text starting with ✏ is guidance about the section — replace it with your content", "howto-list"),
      numberedItem("Orange italic text starting with ⚑ Gap is a specific item this draft could not confirm from its source — resolve it, don't delete it silently", "howto-list"),
      numberedItem("Tables with sample rows show format; add or remove rows as needed", "howto-list"),
      numberedItem("Mark the document status clearly (Draft → In Review → Approved) as it evolves", "howto-list"),
      numberedItem("Version-control this document; date every significant revision", "howto-list"),
      ...(CONTENT.sourceAttribution ? [spacer(6), bodyText(CONTENT.sourceAttribution, { italics: true, color: "555555" })] : []),
      spacer(24),

      // ── 1. PURPOSE & CONTEXT ───────────────────────────────────────────────
      sectionTitle("1 · Purpose & Context"),
      spacer(6),
      subTitle("1.1  Problem Statement"),
      bodyText("Describe the problem this product or feature solves. Be specific about who experiences it, how frequently, and what the cost of not solving it is."),
      spacer(4),
      guidance("Write 2–4 sentences. Avoid solution language here — stay focused on the problem. A good test: could you read this to a customer and have them nod in recognition?"),
      spacer(4),
      bodyText(CONTENT.problemStatement.text),
      ...renderGaps(CONTENT.problemStatement.gaps),
      ...renderConflicts(CONTENT.problemStatement.conflicts),
      spacer(12),

      subTitle("1.2  Business Objectives"),
      bodyText("State the business goals this initiative supports. These should connect directly to company OKRs or strategic priorities."),
      spacer(4),
      guidance("Each objective should be measurable. Link to the OKR or strategic priority it supports where possible."),
      spacer(4),
      ...CONTENT.businessObjectives.bullets.map(b => numberedItem(b, "business-objectives")),
      ...renderGaps(CONTENT.businessObjectives.gaps),
      ...renderConflicts(CONTENT.businessObjectives.conflicts),
      spacer(12),

      subTitle("1.3  Success Metrics (KPIs)"),
      bodyText("Define how you will measure success. These metrics should be observable within a reasonable timeframe post-launch."),
      spacer(8),
      kpiTable(),
      ...renderGaps(CONTENT.kpiGaps),
      ...renderConflicts(CONTENT.kpiConflicts),
      spacer(8),
      guidance("Avoid vanity metrics (e.g. 'total signups'). Prefer leading indicators over lagging ones. Each metric needs a baseline, a target, and a timeframe. If the source doesn't state one of these, write 'TBD — not stated in source' rather than inventing a plausible number."),
      spacer(12),

      subTitle("1.4  Scope"),
      bodyText("Be explicit about what is in scope and what is not. Ambiguity here is the leading cause of scope creep."),
      spacer(4),
      new Paragraph({
        children: [new TextRun({ text: "In Scope", bold: true, size: 22, color: BLACK })],
        spacing: { before: 80, after: 60 },
      }),
      ...CONTENT.scope.inScope.map(b => numberedItem(b, "scope-in-scope")),
      spacer(4),
      new Paragraph({
        children: [new TextRun({ text: "Out of Scope", bold: true, size: 22, color: BLACK })],
        spacing: { before: 80, after: 60 },
      }),
      ...CONTENT.scope.outOfScope.map(b => numberedItem(b, "scope-out-of-scope")),
      ...renderGaps(CONTENT.scope.gaps),
      ...renderConflicts(CONTENT.scope.conflicts),
      spacer(4),
      guidance("The 'out of scope' section is as important as 'in scope'. Be specific — a vague 'custom features' exclusion will generate arguments. Name the things you are intentionally NOT building."),
      spacer(24),

      // ── 2. USER UNDERSTANDING ──────────────────────────────────────────────
      sectionTitle("2 · User Understanding"),
      spacer(6),
      subTitle("2.1  Target Personas"),
      bodyText("Define the primary and secondary users of this product. Personas should reflect real user research, not assumptions."),
      spacer(4),
      guidance("Include 2–4 personas. Each should cover: who they are, their primary goal, their pain point, and a relevant quote if available from user research. The primary persona is always the end user of the product being described — never the person authoring this PRD."),
      spacer(8),
      personaTable(),
      ...renderGaps(CONTENT.personas.gaps),
      ...renderConflicts(CONTENT.personas.conflicts),
      spacer(12),

      subTitle("2.2  User Stories"),
      bodyText("Capture the key interactions as user stories. Format: As a [persona], I want to [action] so that [outcome]."),
      spacer(8),
      userStoryTable(),
      ...renderGaps(CONTENT.userStoryGaps),
      ...renderConflicts(CONTENT.userStoryConflicts),
      spacer(8),
      guidance("Write stories from the user's perspective, not the system's. Acceptance criteria are what QA will test — be specific enough to be testable."),
      spacer(12),

      subTitle("2.3  Current Workflow & Pain Points"),
      bodyText("Map the current state: how do users accomplish this today, and where does it break down?"),
      spacer(4),
      guidance("A simple before/after or step-by-step breakdown works well here. Include data from user interviews, support tickets, or analytics where available."),
      spacer(4),
      currentWorkflowTable(),
      ...renderGaps(CONTENT.currentWorkflowGaps),
      ...renderConflicts(CONTENT.currentWorkflowConflicts),
      spacer(24),

      // ── 3. REQUIREMENTS ────────────────────────────────────────────────────
      sectionTitle("3 · Requirements"),
      spacer(6),
      subTitle("3.1  Priority Framework (MoSCoW)"),
      bodyText("All requirements in this document are prioritized using the MoSCoW method. Every requirement must be assigned a priority — no requirements are assumed to be equal."),
      spacer(8),
      moscowTable(),
      spacer(12),

      subTitle("3.2  Functional Requirements"),
      bodyText("What the product must do. Each requirement should be independently testable."),
      spacer(8),
      requirementsTable(),
      ...renderGaps(CONTENT.requirementGaps),
      ...renderConflicts(CONTENT.requirementConflicts),
      spacer(8),
      guidance("Common mistakes: (1) requirements that describe the UI rather than the behavior, (2) requirements with 'and' in them — split these, (3) vague words like 'fast', 'easy', or 'robust' without a measurable definition."),
      spacer(12),

      subTitle("3.3  Non-Functional Requirements"),
      bodyText("Constraints and quality attributes — how the system must behave, not just what it must do. This section covers qualities the system itself must exhibit (security, performance, compliance). External limitations on how it can be built (tooling, other teams, contracts) belong in Section 5.1 instead."),
      spacer(4),
      nfrTable(),
      ...renderGaps(CONTENT.nfrGaps),
      ...renderConflicts(CONTENT.nfrConflicts),
      spacer(24),

      // ── 4. DESIGN & EXPERIENCE ─────────────────────────────────────────────
      sectionTitle("4 · Design & Experience"),
      spacer(6),
      subTitle("4.1  Design References"),
      guidance("Link to Figma, Sketch, or other design files. Do not embed screenshots as the source of truth — they go stale. Link to the live design file."),
      spacer(4),
      ...CONTENT.designReferences.bullets.map(b => numberedItem(b, "design-references")),
      ...renderGaps(CONTENT.designReferences.gaps),
      ...renderConflicts(CONTENT.designReferences.conflicts),
      spacer(12),

      subTitle("4.2  Key User Flows"),
      bodyText("Describe the primary flows end-to-end. Use numbered steps for clarity. Link to the corresponding Figma frame for each flow."),
      spacer(4),
      guidance("Cover: happy path first, then the most common error states. Every flow should have a clear start, middle, and end state."),
      spacer(4),
      ...CONTENT.userFlows.flatMap((flow, i) => [
        new Paragraph({ children: [new TextRun({ text: flow.title, bold: true, size: 22 })], spacing: { before: 80, after: 60 } }),
        ...flow.steps.map(s => numberedItem(s, `userflow-steps-${i}`)),
        spacer(8),
      ]),
      ...renderGaps(CONTENT.userFlowGaps),
      ...renderConflicts(CONTENT.userFlowConflicts),

      subTitle("4.3  Edge Cases & Error States"),
      bodyText("List the non-happy-path scenarios that must be designed and built. These are the most commonly skipped part of a PRD."),
      spacer(4),
      guidance("For each edge case: describe the trigger condition, the expected system behavior, and the user-facing message or recovery path."),
      spacer(4),
      edgeCaseTable(),
      ...renderGaps(CONTENT.edgeCaseGaps),
      ...renderConflicts(CONTENT.edgeCaseConflicts),
      spacer(24),

      // ── 5. TECHNICAL GUIDANCE ──────────────────────────────────────────────
      sectionTitle("5 · Technical Guidance"),
      spacer(6),
      subTitle("5.1  Constraints & Dependencies"),
      guidance("List any technical constraints the engineering team must work within. Include hard constraints (must use X platform) and soft constraints (prefer Y approach for consistency). Flag dependencies on other teams or third parties. This is about external limits on the build, not qualities of the system — those belong in 3.3."),
      spacer(4),
      constraintsTable(),
      ...renderGaps(CONTENT.constraintsGaps),
      ...renderConflicts(CONTENT.constraintsConflicts),
      spacer(12),

      subTitle("5.2  Data Requirements & Privacy"),
      bodyText("Describe what data is created, consumed, or transformed by this product. Flag any privacy or compliance implications."),
      spacer(4),
      ...CONTENT.dataPrivacy.bullets.map(b => numberedItem(b, "data-privacy")),
      ...renderGaps(CONTENT.dataPrivacy.gaps),
      ...renderConflicts(CONTENT.dataPrivacy.conflicts),
      spacer(4),
      guidance("Flag any data that is personally identifiable (PII), financially sensitive, or subject to regional regulation. Escalate to Legal/Privacy before finalizing."),
      spacer(12),

      subTitle("5.3  Integration Points"),
      bodyText("List all systems this product must connect to, with the nature of the integration."),
      spacer(4),
      ...CONTENT.integrationPoints.bullets.map(b => numberedItem(b, "integration-points")),
      ...renderGaps(CONTENT.integrationPoints.gaps),
      ...renderConflicts(CONTENT.integrationPoints.conflicts),
      spacer(24),

      // ── 6. EXECUTION ──────────────────────────────────────────────────────
      sectionTitle("6 · Execution"),
      spacer(6),
      subTitle("6.1  Milestones & Timeline"),
      bodyText("Map the key delivery milestones. Dates should be agreed with Engineering and Design before publishing this document."),
      spacer(8),
      milestonesTable(),
      ...renderGaps(CONTENT.milestoneGaps),
      ...renderConflicts(CONTENT.milestoneConflicts),
      spacer(8),
      guidance("Avoid committing to dates in this document until Engineering has done at minimum a rough sizing. Preserve the source's own precision — only convert a relative reference into a calendar date when the anchor and unit are both unambiguous. Don't invent day-level precision from vague terms."),
      spacer(12),

      subTitle("6.2  Stakeholders & Sign-Off"),
      bodyText("Identify who is responsible for this initiative and who must approve it before work begins."),
      spacer(8),
      stakeholderTable(),
      ...renderGaps(CONTENT.stakeholderGaps),
      ...renderConflicts(CONTENT.stakeholderConflicts),
      spacer(12),

      subTitle("6.3  Open Questions"),
      bodyText("Capture unresolved questions that could affect scope, design, or feasibility. Assign each to an owner with a deadline."),
      spacer(8),
      questionsTable(),
      ...renderGaps(CONTENT.questionGaps),
      ...renderConflicts(CONTENT.questionConflicts),
      spacer(12),

      subTitle("6.4  Decision Log"),
      bodyText("Record significant decisions made during the PRD process, including what was decided and why. This prevents relitigating past decisions."),
      spacer(8),
      decisionsTable(),
      ...renderGaps(CONTENT.decisionGaps),
      ...renderConflicts(CONTENT.decisionConflicts),
      spacer(24),

      // ── APPENDIX ───────────────────────────────────────────────────────────
      sectionTitle("Appendix"),
      spacer(6),
      subTitle("A.  Version History"),
      versionHistoryTable(),
      spacer(12),

      subTitle("B.  Glossary"),
      guidance("Define any acronyms or domain-specific terms used in this document. The reader should not need prior product knowledge to understand this PRD."),
      spacer(4),
      glossaryTable(),
      spacer(12),

      subTitle("C.  Related Documents"),
      ...CONTENT.relatedDocuments.bullets.map(b => numberedItem(b, "related-documents")),
      ...renderGaps(CONTENT.relatedDocuments.gaps),
      ...renderConflicts(CONTENT.relatedDocuments.conflicts),
      spacer(12),

      subTitle("D.  Intake Readiness Scorecard (Pre-Draft vs. Post-Draft)"),
      bodyText("Compares the intake readiness score from the start of this draft (SKILL.md Step 2.2) against a re-score of this document's actual content and gaps at delivery time. Advisory only — never a gate on delivery."),
      spacer(4),
      ...(CONTENT.preDraftScorecard ? [] : [
        bodyText("No pre-draft score was captured for this draft — scored intake was introduced in Changeset 3A, so this may be a PRD generated (or revised) before scoring existed. Only the Post-Draft column below reflects this draft's actual content.", { italics: true, color: "555555" }),
        spacer(4),
      ]),
      // Item 3 (Changeset 3C clarity fix): one-line legend so the Post-Draft
      // column is never mistaken for a re-graded quality score.
      bodyText("Post-Draft reflects whether any gap or conflict is still flagged in this section — not a re-graded quality score. A single minor open item shows as unresolved even if most of the section is fully specified.", { italics: true, color: "555555" }),
      spacer(4),
      appendixDTable(),

    ],
  }],
});

Packer.toBuffer(doc).then(buffer => {
  fs.writeFileSync("/home/claude/prd-output.docx", buffer);
  console.log("Done: prd-output.docx");
});
