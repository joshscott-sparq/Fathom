import { useEffect, useState } from "react";
import { api } from "../api";
import type { Variables } from "../types";

// Grouped to match variables.yaml's own comment sections, so this settings
// page and the data file read the same way side by side.
const GROUPS: { title: string; hint?: string; fields: { key: keyof Variables; label: string; step?: number }[] }[] = [
  {
    title: "PERT weights",
    fields: [
      { key: "real_weight", label: "Realistic weight", step: 0.05 },
      { key: "opt_weight", label: "Optimistic weight", step: 0.05 },
      { key: "pes_weight", label: "Pessimistic weight", step: 0.05 },
    ],
  },
  {
    title: "Hierarchy multipliers",
    fields: [
      { key: "epic_multiplier", label: "Epic multiplier" },
      { key: "feature_multiplier", label: "Feature multiplier" },
    ],
  },
  {
    title: "Velocity",
    fields: [
      { key: "avg_story_pts", label: "Avg. story points / engineer / sprint" },
      { key: "ai_boost_min", label: "AI boost (min)", step: 0.05 },
      { key: "ai_boost_max", label: "AI boost (max)", step: 0.05 },
      { key: "days_per_story_point", label: "Days per story point", step: 0.25 },
    ],
  },
  {
    title: "Capacity ratios",
    fields: [
      { key: "ba_ratio", label: "BA ratio", step: 0.05 },
      { key: "designer_ratio", label: "Designer ratio", step: 0.05 },
      { key: "devops_ratio", label: "DevOps ratio", step: 0.05 },
      { key: "qa_ratio", label: "QA ratio", step: 0.05 },
    ],
  },
  {
    title: "Time constants",
    fields: [
      { key: "hours_per_sprint", label: "Hours / sprint" },
      { key: "weeks_in_sprint", label: "Weeks / sprint" },
      { key: "working_month_days", label: "Working days / month" },
      { key: "hours_per_day", label: "Hours / day" },
    ],
  },
  {
    title: "Risk impact ladder",
    hint: "Velocity penalty applied per Risk entry, by severity (Context Panel > Risks).",
    fields: [
      { key: "risk_impact_low", label: "Low", step: 0.05 },
      { key: "risk_impact_moderate", label: "Moderate", step: 0.05 },
      { key: "risk_impact_high", label: "High", step: 0.05 },
      { key: "risk_impact_extreme", label: "Extreme", step: 0.05 },
    ],
  },
  {
    title: "Accelerator impact ladder",
    hint: "Velocity offset applied per Accelerator entry, by severity (Context Panel > Accelerators).",
    fields: [
      { key: "accelerator_impact_low", label: "Low", step: 0.05 },
      { key: "accelerator_impact_moderate", label: "Moderate", step: 0.05 },
      { key: "accelerator_impact_high", label: "High", step: 0.05 },
      { key: "accelerator_impact_extreme", label: "Extreme", step: 0.05 },
    ],
  },
];

export function VariablesView() {
  const [values, setValues] = useState<Variables | null>(null);
  const [overridden, setOverridden] = useState<Set<string>>(new Set());
  const [dirty, setDirty] = useState<Set<string>>(new Set());
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  function refresh() {
    api.getVariables()
      .then((r) => { setValues(r.effective); setOverridden(new Set(r.overridden_fields)); setDirty(new Set()); })
      .catch((e) => setError(String(e)));
  }
  useEffect(refresh, []);

  function setField(key: keyof Variables, raw: string) {
    const n = parseFloat(raw);
    if (Number.isNaN(n)) return;
    setValues((v) => (v ? { ...v, [key]: n } : v));
    setDirty((d) => new Set(d).add(key));
  }

  async function save() {
    if (!values || dirty.size === 0) return;
    setSaving(true);
    setError(null);
    try {
      const overrides: Partial<Variables> = {};
      for (const key of dirty) (overrides as any)[key] = (values as any)[key];
      await api.updateVariables(overrides);
      refresh();
    } catch (e) {
      setError(String(e));
    } finally {
      setSaving(false);
    }
  }

  if (!values) return <div className="text-muted text-sm">Loading…</div>;

  return (
    <div className="card">
      <h2 className="card-h">
        Variables
        {dirty.size > 0 && <span className="normal-case tracking-normal text-brand-orange-deep ml-2">unsaved changes</span>}
      </h2>
      <p className="text-[13px] text-muted mt-0 mb-3">
        Org-wide defaults for every new or rebuilt estimate. An estimate can further tune these for itself
        under its own Shape It tab — those per-estimate tweaks don't change what's set here.
      </p>
      {error && <div className="text-brand-orange-deep text-[13px] mb-2">{error}</div>}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {GROUPS.map((g) => (
          <div key={g.title} className="border border-line rounded-xl p-3">
            <div className="text-[12px] uppercase text-muted font-semibold mb-1">{g.title}</div>
            {g.hint && <p className="text-[12px] text-muted mt-0 mb-2">{g.hint}</p>}
            {g.fields.map((f) => (
              <div key={f.key} className="flex items-center justify-between gap-2 py-1 text-[13px]">
                <label className="flex items-center gap-1.5">
                  {f.label}
                  {overridden.has(f.key) && <span className="badge bg-brand-aurora text-brand-deepest">custom</span>}
                </label>
                <input
                  type="number"
                  step={f.step ?? 1}
                  className="field !w-24 !py-1 !px-1.5 text-[13px]"
                  value={values[f.key] as number}
                  onChange={(e) => setField(f.key, e.target.value)}
                />
              </div>
            ))}
          </div>
        ))}
      </div>
      <div className="flex items-center gap-2 mt-3">
        <button className="btn btn-primary text-[13px]" disabled={dirty.size === 0 || saving} onClick={save}>
          {saving ? "Saving…" : "Save changes"}
        </button>
      </div>
    </div>
  );
}
