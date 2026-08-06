// Shapes mirrored from the FastAPI responses. The graph is deep; the UI types the
// fields it uses and leaves the rest loose.

export interface Percentiles {
  p10: number;
  p50: number;
  p80: number;
  p90: number;
}

export interface MonteCarlo {
  iterations: number;
  effort_points: Percentiles;
  duration_sprints: Percentiles;
  cost: Percentiles;
}

export interface Reconciliation {
  top_down_points: number;
  bottom_up_points: number;
  blended_points?: number | null;
}

export interface LinkedFactor {
  family: string;
  severity: string;
  impact: number;
}

export interface Role {
  discipline: string;
  tier: string;
  location: string;
  allocated: number;
  day_rate: number;
}

export interface Component {
  id: string;
  name: string;
  component_type: string;
  technology?: string | null;
  discipline?: string | null;
}

export interface Scenario {
  id: string;
  name: string;
  dev_model: string;
  location_mix: Record<string, number>;
  engineers: number | null;
}

export interface ScenarioResult {
  scenario: Scenario;
  assumptions: string[];
  effort_points: Percentiles;
  duration_sprints: Percentiles;
  cost: Percentiles;
  monthly_cost: number;
  total_cost: number;
}

export interface TeamSuggestion {
  goal: string;
  scenario: Scenario;
  rationale: string;
  result: ScenarioResult | null;
}

export interface DeferralSuggestion {
  work_item_id: string;
  feature: string;
  points: number;
  rationale: string;
  est_sprint_saving: number;
}

export interface ThreePoint {
  realistic: number;
  optimistic?: number | null;
  pessimistic?: number | null;
}

export interface WorkItem {
  id: string;
  level: "epic" | "feature" | "story";
  epic: string;
  feature?: string | null;
  story?: string | null;
  parent_id?: string | null;
  phase_id?: string | null;
  points: ThreePoint;
  practice?: string | null;
  discipline?: string | null;
  tshirt?: string | null;
  cure?: {
    complexity: number; unknowns: number; risks: number; effort: number;
    rationale: string; confidence: number;
  };
  linked_factors?: LinkedFactor[];
  extraction_confidence: number;
  notes?: string | null;
  reference?: string | null;
}

export interface ContextEntry {
  id: string;
  tab: "requirements" | "risks" | "accelerators" | "assumptions";
  source_type: "manual" | "file" | "url";
  content: string;
  reference?: string | null;
  scope: string; // "estimate" or a phase id
  status: "ingested" | "processing" | "error";
  created_at?: string;
  duplicate_of?: string | null;
}

export interface ContextPhase {
  id: string;
  name: string;
  method: "dates" | "duration" | "relative";
  start_date?: string | null;
  end_date?: string | null;
  duration_weeks?: number | null;
  description?: string;
}

export interface ExternalSource {
  id: string;
  type: "sparqos" | "speckit" | "github" | "salesforce" | "notion" | "slack" | "other";
  display_name: string;
  status: "connected" | "needs_authentication" | "error";
  access_mode: "read-only" | "read-write";
  config: Record<string, string>;
  created_at?: string;
}

export interface ContextPanel {
  requirements: ContextEntry[];
  risks: ContextEntry[];
  accelerators: ContextEntry[];
  assumptions: ContextEntry[];
  phases: ContextPhase[];
  external_sources: ExternalSource[];
  pinned_work_items: WorkItem[];
}

export interface Graph {
  project_name: string;
  context_panel?: ContextPanel;
  tags?: string[];
  complexity_factors?: LinkedFactor[];
  scenarios?: ScenarioResult[];
  requirements: { id: string; text: string }[];
  capabilities: { id: string; name: string }[];
  components: Component[];
  work_items: WorkItem[];
  matched_pattern_ids: string[];
  ranked_matches: { pattern_id: string; score: number; rationale: string }[];
  team_plan: { roles: Role[]; monthly_cost?: number; total_cost?: number };
  monte_carlo?: MonteCarlo;
  reconciliation?: Reconciliation;
  deterministic?: { total_points: number; total_cost?: number };
  assumptions: string[];
  client_context: {
    tech_stack: string[];
    compliance_posture: string[];
    team_skills: string[];
  };
}

export interface Reference {
  estimate_id: string;
  project_name: string;
  similarity: number;
  why: string;
  cost_p50?: number | null;
  effort_p50?: number | null;
}

export interface EstimateResponse {
  estimate_id: string;
  version: number;
  graph: Graph;
  mermaid: string;
  references: Reference[];
  opportunity_id?: string | null;
}

export interface EstimateSummary {
  estimate_id: string;
  project_name: string;
  version: number;
  pattern_ids: string[];
  cost_p50?: number | null;
  effort_p50?: number | null;
  updated_at: string;
  tags?: string[] | null;
}

export interface Pattern {
  id: string;
  name: string;
  description: string;
  when_to_use: string;
}

export interface AiTier {
  key: string;
  name: string;
  tier: number;
  human_ratio: number;
  ai_ratio: number;
  human_role: string;
  ai_role: string;
  ai_boost: number;
  effort_multiplier: number;
  assumptions: string[];
}
