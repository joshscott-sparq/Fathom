import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../api";
import type { EstimateSummary } from "../types";

const money = (n?: number | null) =>
  n == null ? "—" : new Intl.NumberFormat("en-US", { style: "currency", currency: "USD", maximumFractionDigits: 0 }).format(n);

export function Dashboard({ userName, canCreate, seeding = false }: {
  userName: string;
  canCreate: boolean;
  seeding?: boolean;
}) {
  const navigate = useNavigate();
  const [estimates, setEstimates] = useState<EstimateSummary[] | null>(null);
  const [oppCount, setOppCount] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api.listEstimates().then(setEstimates).catch((e) => setError(String(e)));
    api.listOpportunities().then((o) => setOppCount(o.length)).catch(() => {});
  }, []);

  const totalValue = (estimates ?? []).reduce((sum, e) => sum + (e.cost_p50 ?? 0), 0);
  const recent = [...(estimates ?? [])].sort((a, b) => b.updated_at.localeCompare(a.updated_at)).slice(0, 6);

  if (error) return <div className="text-brand-orange-deep text-[13px]">{error}</div>;

  return (
    <div>
      <h1 className="text-[24px] font-bold mb-1">Welcome back{userName ? `, ${userName}` : ""}</h1>
      <p className="text-muted text-[14px] mb-5 max-w-2xl">
        Fathom turns a PRD and client context into a live reference architecture, effort estimate,
        cost model, and staffing plan. Start from an Opportunity, add context, and every number updates
        automatically as you go — there's nothing to click "Generate."
      </p>

      <div className="flex items-center gap-2 mb-5 flex-wrap">
        {canCreate && <button className="btn btn-primary text-[13px]" onClick={() => navigate("/new")}>+ New estimate</button>}
        <button className="btn text-[13px]" onClick={() => navigate("/opportunities")}>Browse opportunities</button>
        <button className="btn text-[13px]" onClick={() => navigate("/estimates")}>View all estimates</button>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 mb-6">
        <div className="card mb-0">
          <div className="text-xs text-muted uppercase tracking-wide">Opportunities</div>
          <div className="text-[26px] font-bold tracking-tight">{oppCount ?? "—"}</div>
        </div>
        <div className="card mb-0">
          <div className="text-xs text-muted uppercase tracking-wide">Estimates</div>
          <div className="text-[26px] font-bold tracking-tight">{estimates?.length ?? "—"}</div>
        </div>
        <div className="card mb-0">
          <div className="text-xs text-muted uppercase tracking-wide">Pipeline value (P50)</div>
          <div className="text-[26px] font-bold tracking-tight">{estimates ? money(totalValue) : "—"}</div>
        </div>
      </div>

      <div className="card">
        <h2 className="card-h">Recently updated</h2>
        {!estimates && <p className="text-muted text-[13px] m-0">Loading…</p>}
        {estimates && recent.length === 0 && (
          <p className="text-muted text-[13px] m-0">
            {seeding ? "Loading demo data — this updates automatically." : "No estimates yet. Create one from an opportunity."}
          </p>
        )}
        {recent.map((e) => (
          <div key={e.estimate_id} onClick={() => navigate(`/estimates/${e.estimate_id}`)}
            className="flex items-center gap-2 py-2 border-b border-line last:border-0 cursor-pointer hover:text-brand-orange text-[13px]">
            <div className="flex-1">
              <b>{e.project_name}</b>
              <div className="text-muted text-[11px]">{(e.pattern_ids[0] ?? "no pattern")} · v{e.version}</div>
            </div>
            <div className="text-right">{money(e.cost_p50)}</div>
          </div>
        ))}
      </div>
    </div>
  );
}
