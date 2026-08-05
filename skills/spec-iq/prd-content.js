// ─────────────────────────────────────────────────────────────────────────────
// PRD CONTENT — edit THIS FILE to personalize a PRD. Never edit generate-prd.js.
//
// generate-prd.js is fixed structure/rendering code, shared by every PRD this
// skill produces. This file is the only thing that should change between runs.
// That split exists specifically so that personalizing content (this file)
// can never accidentally also change section order, headers, table layout, or
// wording that's supposed to stay identical across every PRD the skill makes.
//
// EXTRACTION RULES (apply these before filling in any field below):
//   1. No fabrication. Never invent a stakeholder, quote, metric, date, or
//      commitment that isn't present in the source material.
//   2. Unknown handling. Any field without direct source support goes in the
//      matching `gaps` array below (rendered as an orange flag) — never filled
//      with plausible-sounding placeholder content instead. EVERY section in
//      this file has a gaps array (either `sectionName.gaps` for object-shaped
//      sections, or a sibling `xGaps` array for row-array sections like
//      `kpiRows` / `kpiGaps`) — there is no section where a missing field can
//      go unflagged. If you're not sure a section has one, check the render
//      call in generate-prd.js for a matching `renderGaps(...)` line before
//      assuming it doesn't need one. (A gap is MISSING information — see rule
//      8 below for CONTRADICTORY information, which is a different case.)
//   3. Verbatim fields (stakeholder names, dates, decisions, direct quotes)
//      must be attributable to the source. Preserve their specificity.
//   4. Synthesis fields (problem statement, objectives) may synthesize across
//      the source but must not introduce facts, figures, or names absent
//      from it.
//   5. Date specificity. Preserve the source's own precision. Only convert a
//      relative reference ("early next week") into a calendar date when both
//      the anchor date and the unit are unambiguous from context. Do not
//      invent day-level precision from vague terms like "a few days out."
//   6. Persona definition. The primary persona is the end user of the
//      product/feature being described — never the person authoring this
//      PRD. If the author and a plausible end user are the same individual,
//      define the persona by their *relationship to the product* (e.g. "BA
//      using the tool"), not by name.
//   7. Section placement. Non-Functional Requirements (3.3) = qualities the
//      system itself must exhibit (security, performance, compliance
//      behavior). Constraints & Dependencies (5.1) = external limitations on
//      how it can be built (tooling availability, other teams, contracts).
//      When in doubt, ask: "is this a property of the system, or a limit
//      imposed on the build?"
//   8. Conflict handling (Changeset 3C). A gap is missing information; a
//      conflict is CONTRADICTORY information — two different launch dates in
//      one transcript, a requirement that contradicts another, etc. Don't
//      pick one value and discard the other, and don't file it as a gap.
//      Every section that has a `gaps` array below has a matching `conflicts`
//      array (same `sectionName.conflicts` / sibling `xConflicts` naming
//      pattern) — put the conflict there instead. Ask the user which value
//      wins, in flow, at the point the conflict is noticed (SKILL.md Step
//      2.3). If it's still unresolved when this file is finalized, leave it
//      in the `conflicts` array — it renders as a `⚠ Conflict` flag (visually
//      distinct from `⚑ Gap`) and pulls that section's Appendix D post-draft
//      level down the same way an open gap does. See
//      docs/scorecard-proposal.md §E.
//
// Never leave a field as its bracketed default (e.g. "[Insert link]"). Every
// default value below must be either replaced with sourced content or moved
// to that section's `gaps` array — never left as-is. See SKILL.md Step 4
// (self-audit) for the check that enforces this.
// ─────────────────────────────────────────────────────────────────────────────

module.exports = {

  // ── Cover ──────────────────────────────────────────────────────────────────
  cover: {
    productName: "Enter product / feature name",
    version: "v0.1 — Draft",
    status: "Draft | In Review | Approved — update as it progresses",
    statusIsGuidance: true,
    authors: "Name, Title",
    lastUpdated: "YYYY-MM-DD",
    targetLaunch: "YYYY-MM-DD or Quarter",
    docTitle: "Product Requirements Document",
    docSubtitle: "A template for defining what to build, why it matters, and how you'll know it succeeded.",
    footerProductLabel: "[Product Name] PRD",
  },

  // ── 1.1 Problem Statement ─────────────────────────────────────────────────
  problemStatement: {
    text: "[Example] Account managers spend an average of 3 hours per week manually compiling client reports from three separate tools. This delays delivery, introduces errors, and reduces time available for strategic client work. As the client base scales past 500 accounts, this process is no longer sustainable.",
    gaps: [], // e.g. "Confirm which audience (internal vs. client-facing) this problem statement is primarily about"
    conflicts: [], // e.g. "Transcript states the problem costs '3 hours/week' but the follow-up email says '5 hours/week' — confirm which figure is authoritative"
  },

  // ── 1.2 Business Objectives ───────────────────────────────────────────────
  businessObjectives: {
    bullets: [
      "Reduce churn by improving customer satisfaction scores (NPS target: +15 pts)",
      "Increase operational efficiency — reduce manual reporting time by 80%",
      "Enable revenue growth by unlocking the enterprise tier offering",
    ],
    gaps: [], // e.g. "No formal OKR was stated in the source — confirm with leadership before treating this as committed"
    conflicts: [], // e.g. "One speaker framed this as a cost-reduction initiative, another as a revenue initiative — confirm which framing leads"
  },

  // ── 1.3 KPIs — each row: [metric, baseline, target, timeframe] ────────────
  // Use exact figures from the source. If the source doesn't state a baseline,
  // target, or timeframe, put "TBD — not stated in source" rather than a
  // number that sounds plausible.
  kpiRows: [
    ["Monthly Active Users (MAU)", "12,000", "20,000", "6 months"],
    ["Task completion rate", "62%", "80%", "3 months"],
  ],
  kpiGaps: [], // e.g. "No baseline was stated in the source for X metric — confirm before treating 12,000 as accurate"
  kpiConflicts: [], // e.g. "Two different MAU targets were stated (20,000 vs. 25,000) in the same meeting — confirm which is authoritative"

  // ── 1.4 Scope ──────────────────────────────────────────────────────────────
  scope: {
    inScope: [
      "Automated report generation for standard report types (weekly, monthly, quarterly)",
      "Integration with existing CRM and analytics platforms",
      "Downloadable PDF and CSV export",
    ],
    outOfScope: [
      "Custom report builder (deferred to v2)",
      "Real-time data streaming (batch processing only in this release)",
      "Mobile app (web only)",
    ],
    gaps: [],
    conflicts: [], // e.g. "One speaker said mobile was out of scope, another referenced a 'mobile-first' requirement later — confirm which stands"
  },

  // ── 2.1 Personas ───────────────────────────────────────────────────────────
  // Remember the persona-definition rule: the end user of the product, not
  // whoever is authoring this PRD.
  personas: {
    primary: {
      label: "Alex — Senior Account Manager",
      goal: "Deliver accurate client reports without manual data wrangling",
      pain: "Spends 3h/week copy-pasting data across tools; prone to errors before big client calls",
      quote: '"I just want one place that pulls everything together automatically."',
      techComfort: "Medium — uses Salesforce and Excel daily",
    },
    secondary: {
      label: "Jordan — Operations Manager",
      goal: "Ensure data accuracy and compliance across all client reporting",
      pain: "No audit trail for manual reports; difficult to catch errors before delivery",
      quote: '"I need to trust the numbers before they go out the door."',
      techComfort: "High — comfortable with admin tools and dashboards",
    },
    gaps: [], // e.g. "Personas inferred from meeting discussion, not formal user research — validate before finalizing"
    conflicts: [], // e.g. "Source describes the primary persona's tech comfort as both 'High' and 'Medium' in different sections — confirm which is accurate"
  },

  // ── 2.2 User Stories — each row: [persona, story, acceptanceCriteria] ─────
  userStoryRows: [
    ["New User", "As a new user, I want to sign up with my email so I can access the platform without needing a company account.", "Can register in < 2 min; receives confirmation email; lands on onboarding flow"],
    ["Admin", "As an admin, I want to manage user roles so I can control who sees sensitive data.", "Role changes take effect immediately; audit log updated; user notified"],
  ],
  userStoryGaps: [], // e.g. "Acceptance criteria for the Admin story were inferred, not stated verbatim in source"
  userStoryConflicts: [], // e.g. "Two different acceptance thresholds were given for the same story (< 2 min vs. < 5 min) — confirm which wins"

  // ── 2.3 Current Workflow — each row: [currentStatePain, desiredFutureState]
  currentWorkflowRows: [
    ["Export data from CRM (10 min)", "Data auto-pulled on schedule"],
    ["Copy into Excel, format manually (45 min)", "Report generated automatically with brand template"],
    ["Cross-check against analytics tool (20 min)", "Single source of truth — no reconciliation needed"],
    ["Email to client, manually track version (5 min)", "One-click send with delivery confirmation logged"],
  ],
  currentWorkflowGaps: [], // e.g. "Time estimates per step were not stated in source — confirm with the team before publishing"
  currentWorkflowConflicts: [], // e.g. "Two speakers gave different time estimates for the same workflow step — confirm which is accurate"

  // ── 3.2 Functional Requirements — each row: [#, category, requirement, priority, notes]
  requirementRows: [
    ["1", "Authentication", "Users must be able to log in with email + password", "M", "Link to design specs"],
    ["2", "Performance", "Page load < 2s on 4G connection", "M", "Benchmark target"],
    ["3", "Accessibility", "WCAG 2.1 AA compliance", "S", "Audit tool TBD"],
  ],
  requirementGaps: [], // e.g. "Priority for requirement #3 was inferred, not explicitly stated by the source — confirm before finalizing"
  requirementConflicts: [], // e.g. "Requirement #2 was called both 'Must Have' and 'Should Have' by different speakers — confirm the actual priority"

  // ── 3.3 Non-Functional Requirements — each row: [category, requirement, priority, metric]
  // This section describes qualities the SYSTEM must exhibit — see Section
  // Placement rule above. Do not put team/tooling/vendor constraints here;
  // those belong in constraintsRows (5.1) instead.
  nfrRows: [
    ["Performance", "API responses < 500ms at p95 under 1,000 concurrent users", "M", "Load test"],
    ["Security", "All data encrypted at rest (AES-256) and in transit (TLS 1.3+)", "M", "Audit"],
    ["Availability", "99.9% uptime SLA; < 4h planned maintenance windows", "M", "SLA report"],
    ["Accessibility", "WCAG 2.1 Level AA compliance", "S", "Axe audit"],
    ["Scalability", "Architecture must support 10× current user volume without redesign", "S", "Capacity plan"],
    ["Data Retention", "User data retained per regional compliance requirements", "M", "Legal sign-off"],
  ],
  nfrGaps: [], // e.g. "Specific uptime SLA and compliance regime were not stated in source"
  nfrConflicts: [], // e.g. "Source stated both a 99.9% and a 99.99% uptime target in different meetings — confirm which SLA is committed"

  // ── 4.1 Design References ─────────────────────────────────────────────────
  designReferences: {
    bullets: [
      "Figma: [Insert link to design file — label which page/frame]",
      "Design system / component library: [Insert link]",
      "Brand guidelines: [Insert link]",
      "Prototype for usability testing: [Insert link if available]",
    ],
    gaps: [], // e.g. "No design files were shared in the source — confirm links with Design before finalizing"
    conflicts: [], // e.g. "Two different Figma links were shared for the same flow — confirm which is current"
  },

  // ── 4.2 Key User Flows ────────────────────────────────────────────────────
  userFlows: [
    {
      title: "Flow 1: Generate a New Report",
      steps: [
        "User navigates to Reports > New Report",
        "Selects report type (Weekly / Monthly / Quarterly) and client",
        "Previews auto-populated data; edits any fields if needed",
        "Clicks 'Generate' — report renders in < 10 seconds",
        "Downloads PDF or sends directly to client via email",
      ],
    },
  ],
  userFlowGaps: [], // e.g. "Only the happy path was described in source — error states were not covered"
  userFlowConflicts: [], // e.g. "Source describes the report-generation flow taking both '< 10 seconds' and '< 30 seconds' — confirm which is accurate"

  // ── 4.3 Edge Cases — each row: [scenario, expectedBehaviour, userMessage] ─
  edgeCaseRows: [
    ["CRM integration returns no data", "Show last-known data with timestamp; surface warning", '"Data last updated [date] — CRM sync pending"'],
    ["User loses network mid-generation", "Auto-save draft; resume on reconnect", '"Your report has been saved. Resuming..."'],
    ["Report generation exceeds 30s", "Cancel + retry with smaller date range suggested", '"This is taking longer than expected. Try a shorter date range."'],
  ],
  edgeCaseGaps: [], // e.g. "Source only described the happy path — no error states were discussed"
  edgeCaseConflicts: [], // e.g. "Two different retry behaviors were described for the same timeout scenario — confirm which is intended"

  // ── 5.1 Constraints & Dependencies — each row: [type, item, details] ──────
  // External limitations on how the product can be built — tooling, other
  // teams, contracts. NOT system qualities — see Section Placement rule.
  constraintsRows: [
    ["Platform", "AWS (existing infra)", "Must deploy within existing AWS account and VPC"],
    ["Integration", "Salesforce CRM API", "v52.0 REST API — rate limit: 100,000 calls/24h"],
    ["Integration", "Google Analytics 4", "Service account auth; data export via BigQuery"],
    ["Dependency", "Design system v3", "Component library must be at v3.x — upgrade not in scope"],
  ],
  constraintsGaps: [], // e.g. "No engineering constraints were discussed in source — confirm with Eng before finalizing"
  constraintsConflicts: [], // e.g. "Source names two different CRM API rate limits in separate discussions — confirm which is current"

  // ── 5.2 Data Requirements & Privacy ───────────────────────────────────────
  dataPrivacy: {
    bullets: [
      "Data ingested: Account performance metrics (CRM), web analytics (GA4), billing data (Stripe)",
      "Data created: Report files (PDF/CSV), delivery logs, user audit trail",
      "PII handling: Client names and email addresses included in reports — subject to GDPR/CCPA",
      "Retention policy: Reports retained for 24 months; audit logs for 7 years",
      "Access control: Reports visible only to assigned account managers and admins",
    ],
    gaps: [],
    conflicts: [], // e.g. "Source gives two different retention periods for report files (24 months vs. 36 months) — confirm which policy applies"
  },

  // ── 5.3 Integration Points ────────────────────────────────────────────────
  integrationPoints: {
    bullets: [
      "Salesforce CRM — read-only (pull account + opportunity data)",
      "Google Analytics 4 — read-only (pull traffic + conversion data)",
      "Stripe — read-only (pull billing/revenue data)",
      "SendGrid — write (trigger report delivery emails)",
      "Internal data warehouse (Snowflake) — read-only (historical data fallback)",
    ],
    gaps: [], // e.g. "No integrations were mentioned in source — confirm with Engineering before finalizing"
    conflicts: [], // e.g. "Source describes the Stripe integration as both read-only and write-capable in different sections — confirm which is correct"
  },

  // ── 6.1 Milestones — each row: [milestone, deliverable, date, owner] ──────
  // Date specificity rule applies: only use a specific date if the source
  // gave one or an unambiguous anchor to derive it from.
  milestoneRows: [
    ["Discovery complete", "Signed-off PRD", "YYYY-MM-DD", "PM"],
    ["Design handoff", "Figma specs + component library", "YYYY-MM-DD", "Design Lead"],
    ["Engineering kickoff", "Sprint plan + story points", "YYYY-MM-DD", "Eng Lead"],
    ["Beta launch", "Feature-complete build", "YYYY-MM-DD", "PM"],
    ["GA launch", "Public release", "YYYY-MM-DD", "PM"],
  ],
  milestoneGaps: [], // e.g. "No dates were agreed in source — TBD pending Engineering sizing"
  milestoneConflicts: [], // e.g. "Two different beta launch dates were stated in the same meeting (2026-09-01 vs. 2026-10-15) — confirm which is committed"

  // ── 6.2 Stakeholders — each row: [name, role, responsibilities, signOff] ──
  stakeholderRows: [
    ["Jane Smith", "Product Manager", "Author, final approval", "Yes"],
    ["Alex Johnson", "Engineering Lead", "Feasibility review", "Yes"],
  ],
  stakeholderGaps: [], // e.g. "No sign-off chain beyond the author was stated in source"
  stakeholderConflicts: [], // e.g. "Source names two different people as 'final approval' for this PRD — confirm who actually signs off"

  // ── 6.3 Open Questions — each row: [#, question, owner, due, status] ──────
  questionRows: [
    ["1", "Do we support SSO at launch?", "Product Lead", "YYYY-MM-DD", "Open"],
    ["2", "What are our data retention requirements?", "Legal", "YYYY-MM-DD", "Open"],
  ],
  questionGaps: [], // e.g. "Owners/due dates for these questions were not stated in source"
  questionConflicts: [], // e.g. "Source records two contradictory answers to the same open question in different meetings — confirm which stands"

  // ── 6.4 Decision Log — each row: [date, decision, rationale, owner] ───────
  decisionRows: [
    ["YYYY-MM-DD", "Chose React over Vue", "Team familiarity; ecosystem support", "Eng Lead"],
  ],
  decisionGaps: [], // e.g. "No decisions had been formally logged as of this draft"
  decisionConflicts: [], // e.g. "Two decision-log entries record contradictory rationale for the same choice — confirm which is accurate"

  // ── Appendix A. Version History — each row: [version, date, summary, author]
  versionHistoryRows: [
    ["v0.1", "YYYY-MM-DD", "Initial draft", "Author Name"],
  ],

  // ── Appendix B. Glossary — each row: [term, definition] ───────────────────
  glossaryRows: [
    ["MAU", "Monthly Active Users — users who performed at least one meaningful action in the last 30 days"],
    ["MoSCoW", "Prioritisation framework: Must Have / Should Have / Could Have / Won't Have"],
    ["NPS", "Net Promoter Score — customer loyalty metric derived from 'how likely are you to recommend us?'"],
    ["PRD", "Product Requirements Document — this document"],
    ["SLA", "Service Level Agreement — contractual commitment to uptime and performance"],
  ],

  // ── Appendix C. Related Documents ─────────────────────────────────────────
  relatedDocuments: {
    bullets: [
      "Product Strategy / Roadmap: [Link]",
      "User Research Report: [Link]",
      "Technical Architecture Design: [Link]",
      "Competitive Analysis: [Link]",
      "Figma Design File: [Link]",
      "Go-To-Market Plan: [Link]",
    ],
    gaps: [], // e.g. "No related documents were mentioned in the source material"
    conflicts: [], // e.g. "Two different links were given for the same Go-To-Market Plan document — confirm which is current"
  },

  // ── "About this draft" traceability note ──────────────────────────────────
  // Fill this in per the Multi-Format Input Handling convention: source type
  // + identifying metadata for traceability.
  sourceAttribution: null, // e.g. "Drafted from the transcript of the 2026-07-07 SpecIQ standup (Beverly Armstrong, Courtney Cleaver, Britt Chance, Jackson Stakeman)."

  // ── Pre-Draft readiness scorecard (captured, not computed here) ───────────
  // Set this to the object returned by scorecard-config.js's scoreIntake()
  // during SKILL.md Step 2.2, plus a capturedAt date. This is a CAPTURE, not
  // a live value — Step 2.2 computes the score once, shows it to the user,
  // and this field holds that exact result so it can't drift from what the
  // user actually saw.
  //   Shape (when set): {
  //     result: <full scoreIntake() return value — categories, totalEarned,
  //              totalAchievable, percent, percentBand, hardGateFailures, band>,
  //     capturedAt: "YYYY-MM-DD",
  //   }
  // As of Changeset 3B, generate-prd.js reads this field VERBATIM into
  // Appendix D's "Pre-Draft" column — it is never recomputed at render time.
  // If this is null (e.g. a PRD generated or revised before Changeset 3A
  // added scoring), Appendix D renders gracefully: a note that no pre-draft
  // score was captured, and "Not captured" in that column, rather than
  // crashing. The "Post-Draft" column needs no matching field here — it's
  // re-scored entirely at render time from this file's own content and
  // `gaps`/`conflicts` state (see generate-prd.js's scorePostDraft()), reusing
  // the exact same per-section keys (`problemStatement.gaps`/`.conflicts`,
  // `kpiGaps`/`kpiConflicts`, `personas.gaps`/`.conflicts`,
  // `requirementGaps`/`requirementConflicts`, `milestoneGaps`/
  // `milestoneConflicts`, `stakeholderGaps`/`stakeholderConflicts`) as the
  // rest of this file — no new field was needed for it. An unresolved
  // conflict pulls a category's post-draft level down the same way an open
  // gap does (Changeset 3C) — see postDraftCategoryLevel() there.
  preDraftScorecard: null,

};
