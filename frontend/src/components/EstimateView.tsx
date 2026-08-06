import { Fragment, useEffect, useRef, useState } from "react";
import { api } from "../api";
import type { AiTier, DeferralSuggestion, EstimateResponse, Percentiles, TeamSuggestion, WorkItem } from "../types";
import { MermaidDiagram } from "./MermaidDiagram";
import { Section } from "./Section";
import { ShareControls } from "./ShareControls";
import { CommentsSection } from "./CommentsSection";
import { Spinner } from "./Spinner";

let _wiSeq = 0;
const wiUid = () => `wi${Date.now().toString(36)}${_wiSeq++}`;

const DEFAULT_CURE = { complexity: 2, unknowns: 2, risks: 2, effort: 2, rationale: "Manually added.", confidence: 1.0 };

const money = (n: number) =>
  new Intl.NumberFormat("en-US", { style: "currency", currency: "USD", maximumFractionDigits: 0 }).format(n);

// Dummy Salesforce link — real org/instance wiring is a later integration step.
const sfUrl = (kind: "Account" | "Opportunity", sfId: string) => `https://sparq.my.salesforce.com/lightning/r/${kind}/${sfId}/view`;
const pts = (n: number) => `${Math.round(n)} pts`;
const fmtPts = (n: number) => (Number.isInteger(n) ? String(n) : n.toFixed(1));

const TH = "text-left py-1.5 px-2 border-b border-line uppercase text-[12px]";
const TD = "py-1.5 px-2 border-b border-line";

function Stat({ label, value, sub, range, fmt }: { label: string; value: string; sub?: string; range?: Percentiles; fmt?: (n: number) => string }) {
  return (
    <div className="card mb-0">
      <div className="text-xs text-muted uppercase tracking-wide">{label}</div>
      <div className="text-[26px] font-bold tracking-tight">{value} {sub && <span className="text-sm font-medium text-muted">{sub}</span>}</div>
      {range && fmt && <div className="text-xs text-brand-green font-semibold mt-0.5">80% conf: {fmt(range.p10)} – {fmt(range.p80)}</div>}
    </div>
  );
}

function TagBar({ tags, canEdit, onChange }: { tags: string[]; canEdit: boolean; onChange: (t: string[]) => void }) {
  const [input, setInput] = useState("");
  function add() {
    const t = input.trim();
    if (t && !tags.includes(t)) onChange([...tags, t]);
    setInput("");
  }
  return (
    <div className="flex items-center gap-1.5 flex-wrap mb-4">
      <span className="text-[12px] text-muted uppercase tracking-wide mr-1">Tags</span>
      {tags.map((t) => (
        <span key={t} className="badge bg-brand-mint text-brand-sage">
          {t}
          {canEdit && <button className="ml-1 text-muted hover:text-brand-orange-deep" onClick={() => onChange(tags.filter((x) => x !== t))}>×</button>}
        </span>
      ))}
      {tags.length === 0 && !canEdit && <span className="text-muted text-[12px]">none</span>}
      {canEdit && (
        <input className="field !w-32 !py-1 text-[12px]" placeholder="add tag…" value={input}
          onChange={(e) => setInput(e.target.value)} onKeyDown={(e) => e.key === "Enter" && add()} onBlur={add} />
      )}
    </div>
  );
}

export function EstimateView({ initial, canEdit = true, canComment = true, canClone = false, isPublic = false, account, opportunity, onClone }: {
  initial: EstimateResponse; canEdit?: boolean; canComment?: boolean; canClone?: boolean; isPublic?: boolean;
  account?: { name: string; sfId?: string | null };
  opportunity?: { name: string; sfId?: string | null };
  onClone?: (id: string) => void;
}) {
  const readOnly = !canEdit;
  const [est, setEst] = useState(initial);
  const [aiBoost, setAiBoost] = useState(0);
  const [tiers, setTiers] = useState<AiTier[]>([]);
  const [tierKey, setTierKey] = useState<string | null>(null);
  const [engineers, setEngineers] = useState(est.graph.team_plan.roles.filter((r) => r.discipline !== "Project & Program Management").length || 3);
  const [practices, setPractices] = useState<string[]>([]);

  useEffect(() => { api.getRates().then((r) => setPractices(r.practices)).catch(() => {}); }, []);

  useEffect(() => {
    api.listAiTiers().then((ts) => {
      setTiers(ts);
      const match = ts.find((t) => t.ai_boost === aiBoost) ?? ts[0];
      if (match) setTierKey(match.key);
    }).catch(() => {});
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);
  const [subTab, setSubTab] = useState<"shape" | "estimate" | "outputs">("estimate");
  const [oralsMode, setOralsMode] = useState(false);
  const [busy, setBusy] = useState<null | "knobs" | "recost" | "scenarios" | "suggest" | "clone">(null);
  const [team, setTeam] = useState<TeamSuggestion[] | null>(null);
  const [deferrals, setDeferrals] = useState<DeferralSuggestion[] | null>(null);
  const [showShare, setShowShare] = useState(false);
  const [items, setItems] = useState<WorkItem[]>(est.graph.work_items);
  const [savingItems, setSavingItems] = useState(false);
  const [expandedItems, setExpandedItems] = useState<Set<string>>(new Set());

  function toggleExpanded(id: string) {
    setExpandedItems((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id); else next.add(id);
      return next;
    });
  }
  const itemsTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const skipNextItemsSave = useRef(true);

  useEffect(() => {
    setItems(est.graph.work_items);
    skipNextItemsSave.current = true;
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [est.estimate_id, est.version]);

  // Debounced auto-save, mirroring the Context Panel's auto-recalc: edits here
  // are direct hand-edits to the work breakdown, not context to regenerate it.
  useEffect(() => {
    if (!canEdit) return;
    if (skipNextItemsSave.current) { skipNextItemsSave.current = false; return; }
    if (itemsTimer.current) clearTimeout(itemsTimer.current);
    itemsTimer.current = setTimeout(async () => {
      setSavingItems(true);
      try { setEst(await api.updateGraph(est.estimate_id, { ...g, work_items: items })); }
      finally { setSavingItems(false); }
    }, 1000);
    return () => { if (itemsTimer.current) clearTimeout(itemsTimer.current); };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [items]);

  const g = est.graph;
  const mc = g.monte_carlo;
  const rec = g.reconciliation;
  const scenarios = g.scenarios ?? [];
  const phases = g.context_panel?.phases ?? [];

  function updateItem(id: string, patch: Partial<WorkItem>) {
    setItems((prev) => prev.map((it) => it.id === id ? { ...it, ...patch } : it));
  }
  function addItem() {
    setItems((prev) => [...prev, {
      id: wiUid(), level: "story", epic: "New epic", feature: "New feature", story: "New story",
      parent_id: null, phase_id: null, points: { realistic: 0 }, practice: null,
      cure: DEFAULT_CURE, extraction_confidence: 1.0,
    }]);
  }
  function removeItem(id: string) {
    setItems((prev) => prev.filter((it) => it.id !== id && it.parent_id !== id));
  }
  function duplicateItem(id: string) {
    setItems((prev) => {
      const idx = prev.findIndex((it) => it.id === id);
      if (idx === -1) return prev;
      const copy: WorkItem = { ...prev[idx], id: wiUid() };
      return [...prev.slice(0, idx + 1), copy, ...prev.slice(idx + 1)];
    });
  }

  async function applyKnobs(boost = aiBoost) { setBusy("knobs"); try { setEst(await api.recompute(est.estimate_id, { ai_boost: boost, engineer_count: engineers })); } finally { setBusy(null); } }
  function selectTier(t: AiTier) { setTierKey(t.key); setAiBoost(t.ai_boost); applyKnobs(t.ai_boost); }
  async function recost() { setBusy("recost"); try { setEst(await api.recost(est.estimate_id)); } finally { setBusy(null); } }
  async function compareScenarios() { setBusy("scenarios"); try { setEst(await api.computeScenarios(est.estimate_id)); } finally { setBusy(null); } }
  async function loadSuggestions() { setBusy("suggest"); try { const s = await api.suggestions(est.estimate_id); setTeam(s.team); setDeferrals(s.deferrals); } finally { setBusy(null); } }
  async function clone() { setBusy("clone"); try { const c = await api.cloneEstimate(est.estimate_id); onClone?.(c.estimate_id); } finally { setBusy(null); } }
  async function setTags(tags: string[]) { setEst(await api.setTags(est.estimate_id, tags)); }

  const total = rec ? rec.top_down_points + rec.bottom_up_points : 0;
  const bottomPct = total ? (rec!.bottom_up_points / total) * 100 : 50;

  return (
    <div>
      {/* Header with sharing at the top (Google-Drive style) */}
      <div className="flex items-center gap-3 mb-3 flex-wrap">
        <h1 className="m-0 text-[22px] font-bold">{g.project_name}</h1>
        <span className="badge bg-brand-orange/15 text-brand-orange">v{est.version}</span>
        {g.matched_pattern_ids.map((p) => <span key={p} className="badge bg-brand-mint text-brand-sage">{p}</span>)}
        {account && (
          account.sfId
            ? <a href={sfUrl("Account", account.sfId)} target="_blank" rel="noreferrer" className="badge bg-orange-100 text-brand-orange hover:underline" title="Open Account in Salesforce">{account.name} ↗</a>
            : <span className="badge bg-orange-100 text-brand-orange">{account.name}</span>
        )}
        {opportunity && (
          opportunity.sfId
            ? <a href={sfUrl("Opportunity", opportunity.sfId)} target="_blank" rel="noreferrer" className="badge bg-orange-100 text-brand-orange hover:underline" title="Open Opportunity in Salesforce">{opportunity.name} ↗</a>
            : <span className="badge bg-orange-100 text-brand-orange">{opportunity.name}</span>
        )}
        <div className="ml-auto flex items-center gap-2">
          {canEdit && (
            <div className="relative">
              <button className="btn btn-primary text-[13px]" onClick={() => setShowShare((s) => !s)}>Share</button>
              {showShare && (
                <>
                  <div className="fixed inset-0 z-10" onClick={() => setShowShare(false)} />
                  <div className="absolute right-0 mt-1 z-20 bg-surface border border-line rounded-xl p-4 shadow-xl">
                    <ShareControls estimateId={est.estimate_id} />
                  </div>
                </>
              )}
            </div>
          )}
          {canClone && <button className="btn text-[13px] inline-flex items-center gap-1.5" onClick={clone} disabled={busy !== null}>{busy === "clone" ? <><Spinner /> Cloning…</> : "Clone"}</button>}
          <label className="flex items-center gap-1.5 font-medium text-sm"><input type="checkbox" checked={oralsMode} onChange={(e) => setOralsMode(e.target.checked)} /> Client-safe</label>
        </div>
      </div>

      <TagBar tags={g.tags ?? []} canEdit={canEdit} onChange={setTags} />

      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 mb-1">
        <Stat label="Effort" value={mc ? pts(mc.effort_points.p50) : "—"} range={mc?.effort_points} fmt={pts} />
        <Stat label="Duration" value={mc ? mc.duration_sprints.p50.toFixed(1) : "—"} sub="sprints" range={mc?.duration_sprints} fmt={(n) => `${n.toFixed(1)} spr`} />
        {!oralsMode && <Stat label="Cost" value={mc ? money(mc.cost.p50) : "—"} range={mc?.cost} fmt={money} />}
      </div>
      <p className="text-muted text-[11px] mt-1 mb-5">
        Each number is the P50 (median) from the Monte Carlo simulation — the point where half of simulated
        outcomes land above and half below. The range beneath it is the 80% confidence band (P10–P80).
      </p>

      {/* Estimate is the central object: Shape it (levers) -> Estimate (the number itself) -> Outputs (what it produces). */}
      <div className="flex items-center gap-1 border-b border-line mb-5">
        {([
          { key: "estimate", label: "Estimate" },
          { key: "shape", label: "Shape It" },
          { key: "outputs", label: "Outputs" },
        ] as const).map((t) => (
          <button key={t.key} onClick={() => setSubTab(t.key)}
            className={"px-3.5 py-2 text-[13px] font-medium border-b-2 -mb-px " + (subTab === t.key ? "border-brand-orange text-ink" : "border-transparent text-muted hover:text-ink")}>
            {t.label}
          </button>
        ))}
      </div>

      {/* Estimate tab: Top-down/bottom-up and the work breakdown each span full width — */}
      {/* they're the estimate itself, not peer cards competing for column space. */}
      {subTab === "estimate" && (
        <div className="space-y-5">
          {rec && (
            <Section title="Top-down vs bottom-up">
              <div className="flex items-center gap-3 text-[13px]">
                <span>Bottom-up <b>{pts(rec.bottom_up_points)}</b></span>
                <div className="flex-1 h-2 bg-line rounded overflow-hidden relative"><div className="absolute h-full bg-brand-green" style={{ width: `${bottomPct}%` }} /></div>
                <span>Top-down <b>{pts(rec.top_down_points)}</b></span>
              </div>
              {rec.blended_points != null && <p className="text-[13px] mt-2 mb-0">Blended (confidence-weighted): <b>{pts(rec.blended_points)}</b></p>}
              <p className="text-muted text-xs mb-0 mt-1">Divergence widens the range; the blend is the working number.</p>
            </Section>
          )}

          {(items.length > 0 || canEdit) && (() => {
            const parentIds = new Set(items.map((w) => w.parent_id).filter(Boolean));
            const total = items.filter((w) => !parentIds.has(w.id)).reduce((sum, w) => sum + w.points.realistic, 0);
            return (
              <Section title={<>Estimate <span className="normal-case tracking-normal text-muted">(work breakdown)</span></>}
                actions={savingItems ? <span className="text-muted text-[12px] inline-flex items-center gap-1.5 fade-in"><Spinner /> Saving…</span> : undefined}>
                <p className="text-muted text-[12px] mt-0 mb-2">
                  Estimate at the Epic, Feature, or Story level — the blank cells follow the same convention as the
                  legacy workbook. Link a row to a Phase to place it on the timeline.
                </p>
                <div className="overflow-x-auto">
                  <table className="w-full border-collapse text-[13px]">
                    <thead><tr className="text-muted"><th className={TH}></th><th className={TH}>Level</th><th className={TH}>Epic</th><th className={TH}>Feature</th><th className={TH}>Story</th><th className={TH}>Pts (R)</th><th className={TH}>O</th><th className={TH}>P</th><th className={TH}>Phase</th><th className={TH}>Practice</th>{canEdit && <th className={TH}></th>}</tr></thead>
                    <tbody>
                      {items.map((wi) => (
                        <Fragment key={wi.id}>
                        <tr>
                          <td className={TD + " text-center"}>
                            <button className="text-muted hover:text-ink w-5" title={expandedItems.has(wi.id) ? "Hide notes" : "Show notes"} onClick={() => toggleExpanded(wi.id)}>
                              {expandedItems.has(wi.id) ? "▾" : "▸"}
                            </button>
                          </td>
                          <td className={TD}>
                            {canEdit ? (
                              <select className="field !w-24 !py-1 text-[12px]" value={wi.level}
                                onChange={(e) => {
                                  const level = e.target.value as WorkItem["level"];
                                  const patch: Partial<WorkItem> = { level };
                                  if (level === "epic") { patch.feature = null; patch.story = null; }
                                  if (level === "feature") patch.story = null;
                                  updateItem(wi.id, patch);
                                }}>
                                <option value="epic">Epic</option>
                                <option value="feature">Feature</option>
                                <option value="story">Story</option>
                              </select>
                            ) : wi.level}
                          </td>
                          <td className={TD}>
                            {canEdit ? <input className="field !w-44 !py-1 text-[12px]" value={wi.epic} onChange={(e) => updateItem(wi.id, { epic: e.target.value })} /> : wi.epic}
                          </td>
                          <td className={TD}>
                            {canEdit
                              ? (wi.level !== "epic" && <input className="field !w-40 !py-1 text-[12px]" value={wi.feature ?? ""} onChange={(e) => updateItem(wi.id, { feature: e.target.value })} />)
                              : (wi.feature ?? "")}
                          </td>
                          <td className={TD}>
                            {canEdit
                              ? (wi.level === "story" && <input className="field !w-40 !py-1 text-[12px]" value={wi.story ?? ""} onChange={(e) => updateItem(wi.id, { story: e.target.value })} />)
                              : (wi.story ?? "")}
                          </td>
                          <td className={TD}>
                            {canEdit
                              ? <input type="number" className="field !w-16 !py-1 !px-2 text-[12px]" value={wi.points.realistic} onChange={(e) => updateItem(wi.id, { points: { ...wi.points, realistic: parseFloat(e.target.value) || 0 } })} />
                              : fmtPts(wi.points.realistic)}
                          </td>
                          <td className={TD + " text-muted"}>
                            {canEdit
                              ? <input type="number" className="field !w-16 !py-1 !px-2 text-[12px]" value={wi.points.optimistic ?? ""} placeholder={fmtPts(wi.points.realistic)} onChange={(e) => updateItem(wi.id, { points: { ...wi.points, optimistic: e.target.value === "" ? null : parseFloat(e.target.value) } })} />
                              : fmtPts(wi.points.optimistic ?? wi.points.realistic)}
                          </td>
                          <td className={TD + " text-muted"}>
                            {canEdit
                              ? <input type="number" className="field !w-16 !py-1 !px-2 text-[12px]" value={wi.points.pessimistic ?? ""} placeholder={fmtPts(wi.points.realistic)} onChange={(e) => updateItem(wi.id, { points: { ...wi.points, pessimistic: e.target.value === "" ? null : parseFloat(e.target.value) } })} />
                              : fmtPts(wi.points.pessimistic ?? wi.points.realistic)}
                          </td>
                          <td className={TD}>
                            {canEdit ? (
                              <select className="field !w-36 !py-1 text-[12px]" value={wi.phase_id ?? ""} onChange={(e) => updateItem(wi.id, { phase_id: e.target.value || null })}>
                                <option value="">—</option>
                                {phases.map((p) => <option key={p.id} value={p.id}>{p.name}</option>)}
                              </select>
                            ) : (phases.find((p) => p.id === wi.phase_id)?.name ?? "—")}
                          </td>
                          <td className={TD + " text-muted"}>
                            {canEdit ? (
                              <select className="field !w-40 !py-1 text-[12px]" value={wi.practice ?? ""} onChange={(e) => updateItem(wi.id, { practice: e.target.value || null })}>
                                <option value="">—</option>
                                {wi.practice && !practices.includes(wi.practice) && <option value={wi.practice}>{wi.practice}</option>}
                                {practices.map((p) => <option key={p} value={p}>{p}</option>)}
                              </select>
                            ) : (wi.practice ?? "—")}
                          </td>
                          {canEdit && (
                            <td className={TD + " text-center whitespace-nowrap"}>
                              <button className="text-muted hover:text-ink mr-1.5" title="Duplicate row" onClick={() => duplicateItem(wi.id)}>⧉</button>
                              <button className="text-muted hover:text-brand-orange-deep" title="Remove" onClick={() => removeItem(wi.id)}>×</button>
                            </td>
                          )}
                        </tr>
                        {expandedItems.has(wi.id) && (
                          <tr>
                            <td className={TD} colSpan={10 + (canEdit ? 1 : 0)}>
                              <label className="text-muted text-[11px] uppercase block mb-1">Notes</label>
                              <textarea
                                className="w-full bg-transparent resize-none outline-none text-[13px] px-1.5 py-1 rounded border border-line focus:border-brand-orange/60 min-h-[60px]"
                                placeholder="Detail or rationale for this line item…"
                                value={wi.notes ?? ""}
                                disabled={!canEdit}
                                onChange={(e) => updateItem(wi.id, { notes: e.target.value })}
                              />
                              {wi.reference && (
                                <div className="text-muted text-[11px] mt-1">
                                  Source: <span title={wi.reference}>{wi.reference}</span>
                                </div>
                              )}
                            </td>
                          </tr>
                        )}
                        </Fragment>
                      ))}
                    </tbody>
                    <tfoot>
                      <tr className="font-semibold"><td className={TD}></td><td className={TD} colSpan={4}>Total</td><td className={TD}>{pts(total)}</td><td className={TD}></td><td className={TD}></td><td className={TD}></td><td className={TD}></td>{canEdit && <td className={TD}></td>}</tr>
                    </tfoot>
                  </table>
                </div>
                {canEdit && <button className="btn text-[13px] mt-2" onClick={addItem}>+ Add row</button>}
              </Section>
            );
          })()}
        </div>
      )}

      {/* Shape It / Outputs: balanced masonry columns fill cohesively; one column on mobile. */}
      {subTab !== "estimate" && (
        <div className="columns-1 lg:columns-2 gap-5 [&>*]:break-inside-avoid">
          {subTab === "outputs" && (
            <Section title={<>Reference architecture <span className="normal-case tracking-normal text-muted">(Phase 1 sketch)</span></>}>
              <MermaidDiagram code={est.mermaid} />
            </Section>
          )}

          {subTab === "shape" && !readOnly && (
            <Section title="Deal-shaping" expandable={false}>
              <div className="my-1">
                <div className="flex justify-between text-[13px] font-semibold"><span>AI Tier <span className="text-[11px] font-bold text-brand-sage bg-brand-aurora px-1.5 rounded ml-1.5">AI</span></span><span>{Math.round(aiBoost * 100)}% boost</span></div>
                <div className="flex gap-1.5 mt-1.5">
                  {tiers.map((t) => (
                    <button key={t.key} className={"flex-1 py-1.5 rounded-lg text-[13px] font-semibold border " + (tierKey === t.key ? "bg-brand-green text-white border-brand-green" : "border-line text-muted hover:text-ink")}
                      onClick={() => selectTier(t)} disabled={busy !== null} title={`${t.human_role} · AI: ${t.ai_role}`}>
                      {t.tier}
                    </button>
                  ))}
                </div>
                {tierKey && (() => {
                  const t = tiers.find((x) => x.key === tierKey);
                  return t ? <p className="text-muted text-[12px] mt-1.5 mb-0">1 human : {t.ai_ratio} AI — {t.human_role} · AI: {t.ai_role}</p> : null;
                })()}
              </div>
              {tiers.length > 0 && (
                <div className="overflow-x-auto mt-3">
                  <table className="w-full border-collapse text-[12px]">
                    <thead><tr className="text-muted"><th className={TH}>Tier</th><th className={TH}>Human</th><th className={TH}>AI Agents</th><th className={TH}>Human role</th><th className={TH}>AI role</th></tr></thead>
                    <tbody>{tiers.map((t) => (
                      <tr key={t.key} className={tierKey === t.key ? "bg-brand-mint/30" : undefined}>
                        <td className={TD}>{t.tier}</td>
                        <td className={TD}>{t.human_ratio}</td>
                        <td className={TD}>{t.ai_ratio}</td>
                        <td className={TD}>{t.human_role}</td>
                        <td className={TD}>{t.ai_role}</td>
                      </tr>
                    ))}</tbody>
                  </table>
                </div>
              )}
              <div className="my-2">
                <div className="flex justify-between text-[13px] font-semibold"><span>Engineers</span><span>{engineers}</span></div>
                <input type="range" min={1} max={12} step={1} value={engineers} className="w-full accent-brand-orange" onChange={(e) => setEngineers(parseInt(e.target.value))} onMouseUp={() => applyKnobs()} onTouchEnd={() => applyKnobs()} />
              </div>
              <button className="btn w-full mt-1 inline-flex items-center justify-center gap-1.5" onClick={recost} disabled={busy !== null}>{busy === "recost" ? <><Spinner /> Re-costing…</> : "Re-cost with active rates"}</button>
              {busy === "knobs" && <div className="text-muted text-sm mt-2 flex items-center gap-1.5 fade-in"><Spinner /> Recomputing…</div>}
            </Section>
          )}

          {subTab === "shape" && (scenarios.length > 0 || !readOnly) && (
            <Section title="Staffing & development scenarios" actions={!readOnly ? <button className="btn text-[13px] inline-flex items-center gap-1.5" onClick={compareScenarios} disabled={busy !== null}>{busy === "scenarios" ? <><Spinner /> Computing…</> : "Compare models"}</button> : undefined}>
              {scenarios.length === 0 ? (
                <p className="text-muted text-[13px] m-0">Compare AI Tiers (1-5) and US / nearshore / blended staffing on the same scope.</p>
              ) : (
                <div className="overflow-x-auto">
                  <table className="w-full border-collapse text-[13px]">
                    <thead><tr className="text-muted"><th className={TH}>Scenario</th><th className={TH}>Effort</th><th className={TH}>Duration</th>{!oralsMode && <th className={TH}>Cost</th>}</tr></thead>
                    <tbody>{scenarios.map((s) => (<tr key={s.scenario.id}><td className={TD}>{s.scenario.name}<div className="text-muted text-[11px]">{s.assumptions[0]}</div></td><td className={TD}>{pts(s.effort_points.p50)}</td><td className={TD}>{s.duration_sprints.p50.toFixed(1)} spr</td>{!oralsMode && <td className={TD}>{money(s.cost.p50)}</td>}</tr>))}</tbody>
                  </table>
                  <p className="text-muted text-[11px] mt-1.5 mb-0">Figures are each scenario's P50 (median) estimate.</p>
                </div>
              )}
            </Section>
          )}

          {subTab === "outputs" && !oralsMode && (
            <Section title={<>Team plan {g.team_plan.monthly_cost != null && <span className="normal-case tracking-normal text-muted">· {money(g.team_plan.monthly_cost)}/mo</span>}</>} defaultOpen={false}>
              <div className="overflow-x-auto">
                <table className="w-full border-collapse text-[13px]">
                  <thead><tr className="text-muted"><th className={TH}>Discipline</th><th className={TH}>Tier</th><th className={TH}>Loc</th><th className={TH}>Day rate</th></tr></thead>
                  <tbody>{g.team_plan.roles.map((r, i) => (<tr key={i}><td className={TD}>{r.discipline}</td><td className={TD}>{r.tier}</td><td className={TD}>{r.location}</td><td className={TD}>{r.day_rate ? money(r.day_rate) : <span className="text-muted">n/a</span>}</td></tr>))}</tbody>
                </table>
              </div>
            </Section>
          )}

          {subTab === "shape" && (
            <Section title={<>Optimization suggestions <span className="text-[11px] font-bold text-brand-sage bg-brand-aurora px-1.5 rounded ml-1.5">AI</span></>} defaultOpen={false}
              actions={!readOnly ? <button className="btn text-[13px] inline-flex items-center gap-1.5" onClick={loadSuggestions} disabled={busy !== null}>{busy === "suggest" ? <><Spinner /> Thinking…</> : "Suggest"}</button> : undefined}>
              {!team && !deferrals ? (
                <p className="text-muted text-[13px] m-0">Suggests team models that trade cost for speed and features to defer to a later release. Learns from past estimates.</p>
              ) : (
                <div>
                  <h3 className="text-[13px] font-semibold mb-1">Team models</h3>
                  {(team ?? []).map((t, i) => (<div key={i} className="text-[13px] py-2 border-b border-line last:border-0"><span className={"badge mr-1.5 " + (t.goal === "cheaper" ? "bg-brand-mint text-brand-sage" : "bg-brand-orange/15 text-brand-orange")}>{t.goal}</span><b>{t.scenario.name}</b>{t.result && !oralsMode && <span className="text-muted"> — {money(t.result.cost.p50)}, {t.result.duration_sprints.p50.toFixed(1)} spr</span>}<div className="text-muted">{t.rationale}</div></div>))}
                  <h3 className="text-[13px] font-semibold mb-1 mt-3">Defer to a later version</h3>
                  {(deferrals ?? []).map((d, i) => (<div key={i} className="text-[13px] py-2 border-b border-line last:border-0"><b>{d.feature}</b> <span className="text-brand-green font-semibold">−{d.est_sprint_saving.toFixed(1)} spr</span><div className="text-muted">{d.rationale}</div></div>))}
                </div>
              )}
            </Section>
          )}

          {subTab === "outputs" && (
            <Section title="Assumptions & rationale" defaultOpen={false}>
              <ul className="m-0 pl-4 text-[13px] space-y-1">{g.assumptions.map((a, i) => <li key={i}>{a}</li>)}</ul>
            </Section>
          )}
        </div>
      )}

      {!isPublic && (
        <div className="mt-5">
          <Section title="Comments" expandable={false}>
            <CommentsSection estimateId={est.estimate_id} canComment={canComment} />
          </Section>
        </div>
      )}
    </div>
  );
}
