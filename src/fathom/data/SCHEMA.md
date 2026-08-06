# Data files: schema and versioning

All lookup tables live here as versioned YAML. Each file carries a top-level
`version` (semver) and a `source` citing the workbook cell range or spec section
it derives from. Bump `version` when values change; the loader records which
version was used in the exported estimate model.

| File | Source | Contents |
|------|--------|----------|
| `tshirt_scale.yaml` | ResourceLookups!A62:D71 (§2.2) | T-shirt size to points per level |
| `variables.yaml` | VariablesTable + Phases tab (§2.1, 2.3, 2.5) | PERT weights, multipliers, velocity, ratios, time constants, risk impacts |
| `complexity_factors.yaml` | RiskLookups!A44:C152 (§2.4) | Factor families, categories, severity ladders |
| `practices.yaml` | §2.7 | Practice to discipline mapping, discipline tier constraints |
| `tiers.yaml` | §2.6 (Code.gs) | Seniority tiers + weights, locations, priority disciplines |
| `estimate_kinds.yaml` | owner-supplied taxonomy | Semantic kind taxonomy (epic/feature/story/story_point/risk/assumption/accelerator/phase) — definitions, disambiguation, and signals used to classify a piece of extracted text |
| `pricing.example.yaml` | §2.6 (PriceListTable) | **Placeholder** day rates by discipline + tier + location |

## Pricing (PriceListTable) — schema

Pricing is the one table that must NOT be committed with real rates. Real rates
live in `pricing.local.yaml` (gitignored). `pricing.example.yaml` is committed
with obvious placeholder rates so the engine runs out of the box.

Resolution order at load time:
1. `pricing.local.yaml` if present (real rates, never committed).
2. `pricing.example.yaml` fallback (placeholder rates).

### Schema

```yaml
version: "1.0.0"
source: "PriceListTable / §2.6"
currency: "USD"
# Day rate resolved by (discipline, tier, location). location is US or NS (§2.6).
# Monthly resource cost = day_rate * WorkingMonthDays(21) * HoursPerDay(8) is
# applied by the pricing engine (§2.6); rates here are per working day.
rates:
  - { discipline: "Full Stack", tier: "Senior", location: "US", day_rate: 0000 }
  - { discipline: "Full Stack", tier: "Senior", location: "NS", day_rate: 0000 }
  # ... one row per (discipline, tier, location) combination in use
```

A rate row is required for every (discipline, tier, location) a team plan
references. The pricing engine raises a clear error naming any missing
combination rather than guessing.
