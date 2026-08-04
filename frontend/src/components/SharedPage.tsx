import { useEffect, useState } from "react";
import { api } from "../api";
import type { EstimateResponse } from "../types";
import { EstimateView } from "./EstimateView";

export function SharedPage({ token }: { token: string }) {
  const [est, setEst] = useState<EstimateResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api.getShared(token).then(setEst).catch(() => setError("This share link is invalid or has been revoked."));
  }, [token]);

  return (
    <>
      <header className="flex items-center gap-4 px-7 py-3.5 bg-brand-dark text-white">
        <div className="flex items-center gap-3.5">
          <img src="/brand/Sparq-Logo-White.svg" alt="Sparq" className="h-6 w-auto block" />
          <div className="w-px h-5 bg-stone-600" />
          <div className="font-semibold text-base tracking-tight text-white">Fathom</div>
        </div>
        <span className="ml-auto text-[12px] text-stone-300">Shared view (read-only)</span>
      </header>
      <main className="max-w-[1180px] mx-auto px-7 pt-6 pb-16">
        {error && <div className="card text-brand-orange-deep">{error}</div>}
        {!error && !est && <div className="text-muted text-sm">Loading…</div>}
        {est && <EstimateView initial={est} canEdit={false} canComment={false} isPublic />}
      </main>
    </>
  );
}
