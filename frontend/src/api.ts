import type { AiTier, EstimateResponse, EstimateSummary, Graph, Pattern, Variables } from "./types";

// --- Token store (bearer, persisted) ---
const TOKEN_KEY = "aiq_token";
let token: string | null = localStorage.getItem(TOKEN_KEY);

export function setToken(t: string | null) {
  token = t;
  if (t) localStorage.setItem(TOKEN_KEY, t);
  else localStorage.removeItem(TOKEN_KEY);
}
export function getToken() {
  return token;
}

export class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

async function http<T>(path: string, opts: RequestInit = {}): Promise<T> {
  const headers = new Headers(opts.headers);
  if (token) headers.set("Authorization", `Bearer ${token}`);
  const res = await fetch(path, { ...opts, headers });
  if (res.status === 401) {
    setToken(null);
    throw new ApiError(401, "unauthorized");
  }
  if (!res.ok) throw new ApiError(res.status, await res.text());
  const ct = res.headers.get("content-type") || "";
  return (ct.includes("application/json") ? res.json() : res.text()) as Promise<T>;
}

function jsonBody(body: unknown): RequestInit {
  return { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) };
}

export interface AuthUser {
  id: string;
  email: string;
  name: string;
  role: "admin" | "user" | "client";
  auth_provider: string;
}

export interface ClientContextInput {
  tech_stack: string[];
  compliance_posture: string[];
  team_skills: string[];
  us_ns_mix?: Record<string, number>;
}

export const api = {
  // --- Auth ---
  login: (email: string, password: string) =>
    http<{ token: string; user: AuthUser }>("/api/auth/login", jsonBody({ email, password })),
  me: () => http<AuthUser>("/api/auth/me"),
  providers: () => http<{ local: boolean; google: boolean }>("/api/auth/providers"),
  googleLoginUrl: () => http<{ url: string }>("/api/auth/google/login"),

  // --- Patterns / AI tiers ---
  listPatterns: () => http<Pattern[]>("/api/patterns"),
  listAiTiers: () => http<AiTier[]>("/api/ai-tiers"),

  // --- Estimates ---
  listEstimates: () => http<EstimateSummary[]>("/api/estimates"),
  getEstimate: (id: string) => http<EstimateResponse>(`/api/estimates/${id}`),
  getShared: (tok: string) => http<EstimateResponse>(`/api/shared/${tok}`),
  createEstimate: (body: {
    project_name: string;
    prd_text: string;
    client_context: ClientContextInput;
    match_override?: string | null;
    opportunity_id?: string | null;
  }) => http<EstimateResponse>("/api/estimates", jsonBody(body)),
  rebuildEstimate: (id: string, body: {
    project_name: string;
    prd_text: string;
    client_context: ClientContextInput;
    opportunity_id?: string | null;
  }) => http<EstimateResponse>(`/api/estimates/${id}/rebuild`, jsonBody(body)),
  cloneEstimate: (id: string) => http<EstimateResponse>(`/api/estimates/${id}/clone`, { method: "POST" }),
  updateGraph: (id: string, graph: Graph) =>
    http<EstimateResponse>(`/api/estimates/${id}`, { method: "PUT", headers: { "Content-Type": "application/json" }, body: JSON.stringify(graph) }),
  setTags: (id: string, tags: string[]) => http<EstimateResponse>(`/api/estimates/${id}/tags`, jsonBody({ tags })),
  saveContext: (id: string, panel: import("./types").ContextPanel) =>
    http<EstimateResponse>(`/api/estimates/${id}/context`, { method: "PUT", headers: { "Content-Type": "application/json" }, body: JSON.stringify(panel) }),
  ingestUrl: (url: string) => http<{ url: string; text: string; status: string }>("/api/ingest/url", jsonBody({ url })),
  recompute: (id: string, overrides: { ai_boost?: number; engineer_count?: number; variables?: Partial<Variables> }) =>
    http<EstimateResponse>(`/api/estimates/${id}/recompute`, jsonBody(overrides)),
  recost: (id: string) => http<EstimateResponse>(`/api/estimates/${id}/recost`, { method: "POST" }),
  computeScenarios: (id: string) => http<EstimateResponse>(`/api/estimates/${id}/scenarios`, jsonBody({})),
  suggestions: (id: string) =>
    http<{ team: import("./types").TeamSuggestion[]; deferrals: import("./types").DeferralSuggestion[] }>(
      `/api/estimates/${id}/suggestions`,
      { method: "POST" }
    ),
  access: (id: string) => http<{ can_view: boolean; can_comment: boolean; can_edit: boolean }>(`/api/estimates/${id}/access`),

  // --- Sharing / comments ---
  listShares: (id: string) =>
    http<{ shares: { principal_email: string; permission: string }[]; links: { token: string }[] }>(`/api/estimates/${id}/shares`),
  addShare: (id: string, principal: string, permission: string) =>
    http(`/api/estimates/${id}/shares`, jsonBody({ principal, permission })),
  removeShare: (id: string, email: string) =>
    http(`/api/estimates/${id}/shares/${encodeURIComponent(email)}`, { method: "DELETE" }),
  createShareLink: (id: string) => http<{ token: string; path: string }>(`/api/estimates/${id}/share-link`, { method: "POST" }),
  listComments: (id: string) => http<{ author: string; body: string; created_at: string }[]>(`/api/estimates/${id}/comments`),
  addComment: (id: string, body: string) => http(`/api/estimates/${id}/comments`, jsonBody({ body })),

  // --- Context extraction ---
  extractContext: (file: File) => {
    const form = new FormData();
    form.append("file", file);
    return http<{ filename: string; text: string }>("/api/context/extract", { method: "POST", body: form });
  },
  decomposeRequirements: (text: string, existing: string[]) =>
    http<{
      text: string; kind: string; confidence: number; duplicate_of: string | null;
      taxonomy_kind: string; taxonomy_confidence: number; title: string; epic: string;
      priority: "must" | "should" | "could" | "wont" | null;
    }[]>("/api/context/decompose-requirements", jsonBody({ text, existing })),
  summarizeDocument: (text: string) => http<{ summary: string }>("/api/context/summarize", jsonBody({ text })),

  // --- Rate cards ---
  getRates: () =>
    http<{ source: string; summary: { rows: number; disciplines: string[]; locations: string[] }; practices: string[]; rates: { discipline: string; tier: string; location: string; day_rate: number }[] }>("/api/rates"),
  listRateCards: () =>
    http<{ id: string; name: string; is_default: boolean; is_active: boolean; summary: { rows: number; disciplines: string[]; locations: string[] } }[]>("/api/rate-cards"),
  createRateCard: (file: File, name: string) => {
    const form = new FormData();
    form.append("file", file);
    if (name) form.append("name", name);
    return http<{ id: string; name: string }>("/api/rate-cards", { method: "POST", body: form });
  },
  activateRateCard: (id: string) => http(`/api/rate-cards/${id}/activate`, { method: "POST" }),
  deleteRateCard: (id: string) => http(`/api/rate-cards/${id}`, { method: "DELETE" }),
  updateRateCard: (id: string, rows: { discipline: string; tier: string; location: string; day_rate: number }[]) =>
    http<{ id: string; name: string }>(`/api/rate-cards/${id}`, { ...jsonBody({ rows }), method: "PUT" }),

  // --- Variables (D31 tier 1: org-wide defaults, admin-only to write) ---
  getVariables: () => http<{ effective: Variables; overridden_fields: string[] }>("/api/variables"),
  updateVariables: (overrides: Partial<Variables>) =>
    http<{ effective: Variables; overridden_fields: string[] }>("/api/variables", { ...jsonBody(overrides), method: "PUT" }),

  // --- T-shirt scale (D34: org-wide only, admin-only to write) ---
  getTshirtScale: () =>
    http<{ sizes: Record<string, Record<string, number>>; overridden_sizes: string[] }>("/api/tshirt-scale"),
  updateTshirtScale: (overrides: Record<string, Record<string, number>>) =>
    http<{ sizes: Record<string, Record<string, number>>; overridden_sizes: string[] }>("/api/tshirt-scale", { ...jsonBody(overrides), method: "PUT" }),

  // --- Accounts / opportunities / users (admin) ---
  listAccounts: () => http<{ id: string; name: string; sf_account_id?: string }[]>("/api/accounts"),
  createAccount: (name: string, sf_account_id?: string) => http("/api/accounts", jsonBody({ name, sf_account_id })),
  listOpportunities: (accountId?: string) =>
    http<{ id: string; name: string; account_id: string; active_estimate_id?: string; notion_page_ref?: string }[]>(
      "/api/opportunities" + (accountId ? `?account_id=${accountId}` : "")
    ),
  createOpportunity: (body: { name: string; account_id: string; sf_opportunity_id?: string; notion_page_ref?: string }) =>
    http("/api/opportunities", jsonBody(body)),
  getOpportunity: (id: string) =>
    http<{ opportunity: any; account: any; estimates: EstimateSummary[]; notion_notes: { title: string; excerpt: string; url?: string }[] }>(`/api/opportunities/${id}`),
  setActiveEstimate: (oppId: string, estimateId: string) =>
    http(`/api/opportunities/${oppId}/active-estimate?estimate_id=${estimateId}`, { method: "POST" }),
  listUsers: () => http<AuthUser[]>("/api/users"),
  createUser: (body: { email: string; name: string; role: string; password?: string }) => http("/api/users", jsonBody(body)),
  setUserRole: (id: string, role: string) => http(`/api/users/${id}/role?role=${role}`, { method: "POST" }),
  assignClient: (id: string, body: { account_id?: string; opportunity_id?: string }) =>
    http(`/api/users/${id}/assign`, jsonBody(body)),

  // --- Demo ---
  seedDemo: () => http<{ created_count: number; total: number }>("/api/demo/seed", { method: "POST" }),
};
