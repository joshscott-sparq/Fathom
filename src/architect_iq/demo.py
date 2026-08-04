"""Demo-mode seeding.

Populates the store with curated estimates so every surface is visible without
manual entry: all three patterns (distinct architectures/diagrams), a
reference-class pair (shared pattern + tech, so memory retrieval lights up), an
estimate with recorded actuals that tunes the next one's prior, and a
recomputed estimate that shows versioning.

Idempotent by project name: re-seeding skips scenarios already present. Run as
`python -m architect_iq.demo [db_path]` for headless seeding.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .core.recompute import RecomputeOverrides, recompute
from .memory.priors import ActualOutcome
from .models.context import (
    AccessMode, ConnectionStatus, ContextEntry, ContextPanel, ContextPhase, ContextTab,
    ExternalSource, ExternalSourceType, PhaseMethod, SourceType,
)
from .models.org import Permission
from .models.results import ClientContext
from .models.team import RateRow
from .service import EstimateService


@dataclass
class DemoScenario:
    project_name: str
    prd_text: str
    context: ClientContext
    actual_points: float | None = None  # record actuals -> tunes later priors
    recompute: RecomputeOverrides | None = None  # create a v2 to show versioning
    note: str = ""


DEMO_SCENARIOS: list[DemoScenario] = [
    DemoScenario(
        project_name="[Demo] Acme Insurance — Claims Knowledge Assistant",
        prd_text=(
            "- Build a retrieval augmented generation platform over ten years of claims documents\n"
            "- Adjusters query unstructured policy and claim files and receive grounded llm answers with citations\n"
            "- Ingestion and embedding pipelines run on databricks with a managed vector store\n"
            "- Evaluation harness measures answer quality and guards against regressions\n"
            "- Web chat UI for the adjuster team with feedback capture\n"
            "- All data stays within the client tenant for compliance"
        ),
        context=ClientContext(
            tech_stack=["Databricks", "Python", "React"],
            compliance_posture=["SOC 2", "HIPAA"],
            team_skills=["Spark", "LLMs", "React"],
            us_ns_mix={"US": 0.7, "NS": 0.3},
        ),
        actual_points=210,
        note="Delivered actual recorded; tunes the RAG prior for later estimates.",
    ),
    DemoScenario(
        project_name="[Demo] Meridian Bank — Policy Copilot",
        prd_text=(
            "- Retrieval augmented generation copilot over banking policy and procedure documents\n"
            "- Relationship managers ask questions and get grounded answers with source links\n"
            "- Embeddings and retrieval on databricks, vector store for similarity search\n"
            "- Quality evaluation and audit logging for every answer\n"
            "- Internal web UI"
        ),
        context=ClientContext(
            tech_stack=["Databricks", "Azure", "Python"],
            compliance_posture=["SOC 2", "PCI DSS"],
            team_skills=["Spark", "LLMs"],
        ),
        note="Second RAG engagement; shares pattern + Databricks -> memory references the Acme estimate and uses the tuned prior.",
    ),
    DemoScenario(
        project_name="[Demo] Corom Manufacturing — Legacy .NET Modernization",
        prd_text=(
            "- Modernize a fifteen year old .net monolith running the order management system\n"
            "- Strangler-fig decomposition into services behind an api gateway\n"
            "- Extract the pricing, inventory, and fulfillment bounded contexts into services\n"
            "- Migrate the order database to a managed sql store\n"
            "- Stand up ci/cd pipelines and staging plus production environments\n"
            "- No downtime cutover"
        ),
        context=ClientContext(
            tech_stack=[".NET", "SQL Server", "Azure"],
            compliance_posture=["SOC 2"],
            team_skills=[".NET", "Azure DevOps"],
        ),
        recompute=RecomputeOverrides(ai_boost=0.3, engineer_count=7),
        note="Different pattern (distinct architecture diagram); recomputed to v2 to show versioning + deal-shaping.",
    ),
    DemoScenario(
        project_name="[Demo] Helios Logistics — Autonomous Dispatch Agent",
        prd_text=(
            "- Agentic workflow that triages dispatch exceptions and proposes resolutions\n"
            "- Orchestrator calls internal systems as tools over mcp\n"
            "- Tool servers wrap the routing, carrier, and ticketing systems\n"
            "- Guardrail service enforces approval policy before any action\n"
            "- Observability layer traces and evaluates every agent run\n"
            "- Operator UI for human in the loop review and approvals"
        ),
        context=ClientContext(
            tech_stack=["MCP", "Python", "TypeScript"],
            compliance_posture=["SOC 2"],
            team_skills=["Python", "LLMs", "agents"],
        ),
        note="Agentic-on-MCP pattern; third distinct architecture.",
    ),
    DemoScenario(
        project_name="[Demo] Northwind Retail — Support Automation Agent",
        prd_text=(
            "- Agentic assistant that resolves tier-one support tickets autonomously\n"
            "- Orchestration loop plans multi step actions and calls tools over mcp\n"
            "- Mcp tool servers integrate the order, returns, and CRM systems\n"
            "- Guardrails and approval gating for refunds and account changes\n"
            "- Tracing and evaluation for auditability\n"
            "- Agent console for support leads"
        ),
        context=ClientContext(
            tech_stack=["MCP", "TypeScript", "Node"],
            compliance_posture=["SOC 2"],
            team_skills=["TypeScript", "agents"],
        ),
        note="Second agentic engagement; references Helios via shared pattern + MCP.",
    ),
]


def _lead_context_panel(opp, acct) -> ContextPanel:
    """A fully-populated Context Panel for the lead demo estimate (Acme RAG).

    Every tab carries sample data so demo mode exercises the panel end to end.
    External sources link to the opportunity's real Salesforce ids and Notion
    page, plus a source that still needs authentication (so both states show).
    """
    sf_account = acct.sf_account_id if acct else ""
    sf_opp = opp.sf_opportunity_id if opp else ""
    notion_ref = opp.notion_page_ref if opp else ""
    return ContextPanel(
        requirements=[
            ContextEntry(
                id="req-1", tab=ContextTab.REQUIREMENTS, source_type=SourceType.MANUAL,
                content=(
                    "- Build a retrieval augmented generation platform over ten years of claims documents\n"
                    "- Adjusters query unstructured policy and claim files and receive grounded llm answers with citations"
                ),
            ),
            ContextEntry(
                id="req-2", tab=ContextTab.REQUIREMENTS, source_type=SourceType.FILE,
                reference="claims-assistant-prd.pdf",
                content=(
                    "- Ingestion and embedding pipelines run on databricks with a managed vector store\n"
                    "- Evaluation harness measures answer quality and guards against regressions\n"
                    "- Web chat UI for the adjuster team with feedback capture"
                ),
            ),
        ],
        risks=[
            ContextEntry(
                id="rk-1", tab=ContextTab.RISKS, source_type=SourceType.MANUAL, scope="estimate",
                content="Primary claims data owner is on leave in Q3, which slows data access and labeling.",
            ),
            ContextEntry(
                id="rk-2", tab=ContextTab.RISKS, source_type=SourceType.MANUAL, scope="ph-mvp",
                content="PHI handling requires a security review before the MVP ships to real adjusters.",
            ),
        ],
        accelerators=[
            ContextEntry(
                id="ac-1", tab=ContextTab.ACCELERATORS, source_type=SourceType.MANUAL, scope="estimate",
                content="A reference RAG implementation already exists in-house to build from.",
            ),
        ],
        assumptions=[
            ContextEntry(
                id="as-1", tab=ContextTab.ASSUMPTIONS, source_type=SourceType.MANUAL,
                content="Client provisions the Databricks workspace and grants data access by kickoff.",
            ),
        ],
        phases=[
            ContextPhase(id="ph-disc", name="Discovery", method=PhaseMethod.RELATIVE,
                         description="Data access, corpus review, evaluation design."),
            ContextPhase(id="ph-mvp", name="MVP", method=PhaseMethod.DURATION, duration_weeks=8,
                         description="Grounded answers with citations for a pilot adjuster group."),
            ContextPhase(id="ph-v1", name="Version 1", method=PhaseMethod.RELATIVE,
                         description="Full rollout, feedback capture, regression guardrails."),
        ],
        external_sources=[
            ExternalSource(id="es-sparqos", type=ExternalSourceType.SPARQOS, display_name="SparqOS",
                           status=ConnectionStatus.CONNECTED, access_mode=AccessMode.READ),
            ExternalSource(
                id="es-sf", type=ExternalSourceType.SALESFORCE, display_name="Acme — Claims KA (Salesforce)",
                status=ConnectionStatus.CONNECTED, access_mode=AccessMode.READ,
                config={"account": sf_account, "opportunity": sf_opp},
            ),
            ExternalSource(
                id="es-notion", type=ExternalSourceType.NOTION, display_name="Opportunity notes (Notion)",
                status=ConnectionStatus.CONNECTED, access_mode=AccessMode.READ,
                config={"page": notion_ref},
            ),
            ExternalSource(
                id="es-gh", type=ExternalSourceType.GITHUB, display_name="acme/claims-rag (prior work)",
                status=ConnectionStatus.NEEDS_AUTH, access_mode=AccessMode.READ,
                config={"repo": "acme/claims-rag", "branch": "main"},
            ),
        ],
    )


def is_seeded(service: EstimateService) -> bool:
    names = {s.project_name for s in service.list_estimates()}
    return any(sc.project_name in names for sc in DEMO_SCENARIOS)


def _slug(text: str) -> str:
    return "".join(c.lower() if c.isalnum() else "-" for c in text).strip("-")


def seed_demo(service: EstimateService) -> dict:
    """Seed demo scenarios idempotently, with org structure and ownership.

    Each scenario name is `[Demo] <Account> — <Opportunity>`; we create the
    account and opportunity (with Salesforce ids + a Notion page ref), own the
    estimates as the sample user, and assign the sample client to one account so
    role differences are visible in demo mode.
    """
    directory = service.directory
    existing = {s.project_name for s in service.list_estimates()}
    created: list[dict] = []

    sample_user = directory.get_user_by_email("user@teamsparq.com")
    owner_id = sample_user.id if sample_user else None
    accounts = {a.name: a for a in directory.list_accounts()}

    for i, sc in enumerate(DEMO_SCENARIOS):
        if sc.project_name in existing:
            continue
        label = sc.project_name.replace("[Demo] ", "")
        account_name, _, opp_name = label.partition(" — ")
        opp_name = opp_name or account_name

        account = accounts.get(account_name)
        if account is None:
            account = directory.create_account(account_name, sf_account_id=f"001DEMO{i:04d}")
            accounts[account_name] = account
        opp = directory.create_opportunity(
            name=opp_name, account_id=account.id,
            sf_opportunity_id=f"006DEMO{i:04d}",
            notion_page_ref=f"https://www.notion.so/demo-{_slug(opp_name)}",
        )

        stored, refs = service.create_estimate(
            sc.project_name, sc.prd_text, sc.context, owner_id=owner_id, opportunity_id=opp.id, use_llm=False,
        )
        if sc.recompute is not None:
            stored = service.update_estimate(stored.estimate_id, recompute(stored.graph, sc.recompute))
        if sc.actual_points is not None:
            service.record_actuals(ActualOutcome(estimate_id=stored.estimate_id, delivered_points=sc.actual_points))

        created.append({
            "estimate_id": stored.estimate_id, "project_name": sc.project_name,
            "version": stored.version, "pattern_ids": stored.graph.matched_pattern_ids,
            "opportunity_id": opp.id, "references": len(refs),
        })

    # Assign the sample client to the first account so they see read-only estimates.
    client = directory.get_user_by_email("client@teamsparq.com")
    if client and accounts and not directory.visible_opportunity_ids(client.id):
        first = accounts.get("Acme Insurance") or next(iter(accounts.values()))
        directory.assign_client(client.id, account_id=first.id)

    # Model the remaining features on the first newly-created estimate: computed
    # scenarios, a share to the sample user, a public link, and comments.
    if created:
        lead = created[0]["estimate_id"]

        # Populate the Context Panel so every tab is demonstrated with real data
        # (Requirements/Risks/Accelerators/Assumptions/Phases/External Sources).
        opp = directory.get_opportunity(created[0]["opportunity_id"])
        acct = directory.get_account(opp.account_id) if opp else None
        panel = _lead_context_panel(opp, acct)
        try:
            service.recalculate_from_context(lead, panel, use_llm=False)
        except Exception:  # noqa: BLE001 - context recalc is best-effort in seeding
            pass

        try:
            service.compute_scenarios(lead)
        except Exception:  # noqa: BLE001 - scenarios are best-effort in seeding
            pass
        directory.add_share(lead, "user@teamsparq.com", Permission.COMMENT)
        directory.create_share_link(lead, "admin@teamsparq.com")
        directory.add_comment(lead, "Sample Client", "Can we see a nearshore staffing option for this?")
        directory.add_comment(lead, "Administrator", "Added an agentic + nearshore scenario below — ~60% cost reduction.")

        # Metadata tags on the lead estimate.
        lead_stored = service.get_estimate(lead)
        if lead_stored:
            tagged = lead_stored.graph.model_copy(deep=True)
            tagged.tags = ["priority", "RAG", "active-deal"]
            service.repo.overwrite_latest(lead, tagged)

        # Clone the lead to show multiple estimates per opportunity / testing
        # alternative assumptions (the clone is never the active/official one).
        service.clone_estimate(lead, owner_id=owner_id)

        # A second saved rate card (default stays active) to show card management.
        rows, _ = service.active_rates()
        if not any(c.name == "FY26 Nearshore-leaning (demo)" for c in service.list_rate_cards()):
            discounted = [RateRow(discipline=r.discipline, tier=r.tier, location=r.location,
                                  day_rate=round(r.day_rate * 0.85)) for r in rows]
            service.rate_cards.create("FY26 Nearshore-leaning (demo)", discounted, activate=False)

    return {"created": created, "created_count": len(created), "total": len(service.list_estimates())}


def _main() -> None:
    import sys

    db_path = sys.argv[1] if len(sys.argv) > 1 else "architect_iq.db"
    summary = seed_demo(EstimateService(db_path=db_path))
    print(f"Seeded {summary['created_count']} demo estimates into {db_path}. Total: {summary['total']}.")


if __name__ == "__main__":
    _main()
