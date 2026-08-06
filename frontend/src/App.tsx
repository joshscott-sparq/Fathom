import { useEffect, useRef, useState } from "react";
import { Navigate, NavLink, Route, Routes, useLocation, useNavigate, useParams } from "react-router-dom";
import { api } from "./api";
import { useAuth } from "./auth";
import { useTheme } from "./theme";
import { Dashboard } from "./components/Dashboard";
import { NewEstimate } from "./components/NewEstimate";
import { EstimatePage } from "./components/EstimatePage";
import { EstimatesList } from "./components/EstimatesList";
import { RatesView } from "./components/RatesView";
import { VariablesView } from "./components/VariablesView";
import { AdminView } from "./components/AdminView";
import { SettingsLayout } from "./components/Settings";
import { OpportunityView } from "./components/OpportunityView";
import { OpportunitiesList } from "./components/OpportunitiesList";
import { Login } from "./components/Login";
import { SharedPage } from "./components/SharedPage";
import { Avatar } from "./components/Avatar";

const DEMO_MODE = import.meta.env.VITE_DEMO_MODE === "true";

function SharedRoute() {
  const { token } = useParams<{ token: string }>();
  return <SharedPage token={token!} />;
}

function OpportunityRoute({ canCreate }: { canCreate: boolean }) {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  return <OpportunityView id={id!} canCreate={canCreate} onOpenEstimate={(estId) => navigate(`/estimates/${estId}`)} />;
}

export default function App() {
  const { user, loading, login, logout } = useAuth();
  const { theme, toggle } = useTheme();
  const location = useLocation();
  const navigate = useNavigate();
  const [listKey, setListKey] = useState(0);
  const [menu, setMenu] = useState<null | "user">(null);
  const [ctxCollapsed, setCtxCollapsed] = useState(() => localStorage.getItem("aiq_ctx_collapsed") === "1");
  const [demoError, setDemoError] = useState<string | null>(null);
  const [demoSeeding, setDemoSeeding] = useState(false);
  const demoTried = useRef(false);

  function toggleCtx() {
    setCtxCollapsed((c) => { localStorage.setItem("aiq_ctx_collapsed", c ? "0" : "1"); return !c; });
  }

  useEffect(() => {
    if (!DEMO_MODE || demoTried.current || loading || user) return;
    demoTried.current = true;
    setDemoSeeding(true);
    login("admin@teamsparq.com", "admin123")
      .then(() => api.seedDemo())
      .then(() => setListKey((k) => k + 1))
      .catch(() => setDemoError("Couldn't reach the backend on :8000. Start it first (see README Quick start), then reload."))
      .finally(() => setDemoSeeding(false));
  }, [loading, user]);

  if (location.pathname.startsWith("/shared/")) {
    return (
      <Routes>
        <Route path="/shared/:token" element={<SharedRoute />} />
      </Routes>
    );
  }

  if (loading) return <div className="p-10 text-muted">Loading…</div>;
  if (!user) return <Login demoError={demoError} />;

  const isAdmin = user.role === "admin";
  const isClient = user.role === "client";
  const isEstimatePage = location.pathname.startsWith("/estimates/");

  const nav: { to: string; label: string; show: boolean; end?: boolean }[] = [
    { to: "/", label: "Home", show: true, end: true },
    { to: "/opportunities", label: "Opportunities", show: true },
    { to: "/estimates", label: "Estimates", show: true },
    { to: "/settings", label: "Settings", show: !isClient },
  ];
  const navLinkClass = ({ isActive }: { isActive: boolean }) =>
    "px-3 py-1.5 rounded-lg text-[13px] font-medium whitespace-nowrap " +
    (isActive ? "text-white bg-stone-700" : "text-stone-300 hover:text-white");

  return (
    <>
      <header className="flex items-center gap-4 px-5 sm:px-7 py-3 bg-brand-dark text-white relative flex-wrap">
        <div className="flex items-center gap-3.5">
          <img src="/brand/Sparq-Logo-White.svg" alt="Sparq" className="h-6 w-auto block" />
          <div className="w-px h-5 bg-stone-600 hidden sm:block" />
          <button className="font-semibold text-base tracking-tight text-brand-orange shrink-0" onClick={() => navigate("/")}>
            Fathom
          </button>
        </div>

        {/* Persistent top nav — always visible, not tucked behind a menu. */}
        <nav className="flex items-center gap-1 overflow-x-auto">
          {nav.filter((n) => n.show).map((n) => (
            <NavLink key={n.to} to={n.to} end={n.end} className={navLinkClass}>{n.label}</NavLink>
          ))}
        </nav>

        <div className="ml-auto flex items-center gap-2">
          {DEMO_MODE && <span className="hidden sm:inline px-2.5 py-1 rounded-md text-xs font-semibold text-brand-deepest bg-brand-aurora">Demo</span>}

          {/* Avatar dropdown: user-scoped actions (theme, sign out), not primary nav. */}
          <div className="relative">
            <button onClick={() => setMenu(menu === "user" ? null : "user")} className="rounded-full ring-2 ring-transparent hover:ring-stone-600">
              <Avatar name={user.name} size={32} />
            </button>
            {menu === "user" && (
              <>
                <div className="fixed inset-0 z-10" onClick={() => setMenu(null)} />
                <div className="absolute right-0 mt-1 z-20 bg-surface text-ink border border-line rounded-xl py-1 shadow-xl min-w-[240px]">
                  <div className="px-4 py-2 border-b border-line">
                    <div className="text-[12px] text-muted">Signed in as · {user.role}</div>
                    <div className="text-[13px] font-medium truncate">{user.email}</div>
                  </div>
                  <button className="flex items-center gap-2 w-full text-left px-4 py-2 text-[14px] hover:bg-canvas" onClick={() => { toggle(); setMenu(null); }}>
                    {theme === "dark" ? "☀︎ Light mode" : "☾ Dark mode"}
                  </button>
                  <button className="flex items-center gap-2 w-full text-left px-4 py-2 text-[14px] hover:bg-canvas" onClick={logout}>⇥ Sign out</button>
                </div>
              </>
            )}
          </div>
        </div>
      </header>

      <main className={"max-w-[1440px] mx-auto px-5 sm:px-7 pt-6 " + (isEstimatePage ? (ctxCollapsed ? "pb-24" : "pb-[46vh]") : "pb-16")}>
        <Routes>
          <Route path="/" element={<Dashboard userName={user.name} canCreate={!isClient} seeding={demoSeeding} />} />
          <Route path="/opportunities" element={<OpportunitiesList key={listKey} onOpen={(id) => navigate(`/opportunities/${id}`)} seeding={demoSeeding} canCreate={!isClient} />} />
          <Route path="/opportunities/:id" element={<OpportunityRoute canCreate={!isClient} />} />
          <Route path="/estimates" element={<EstimatesList key={listKey} onOpen={(id) => navigate(`/estimates/${id}`)} seeding={demoSeeding} />} />
          <Route path="/estimates/:id" element={<EstimatePage isClient={isClient} ctxCollapsed={ctxCollapsed} onToggleCtx={toggleCtx} />} />
          {!isClient && <Route path="/new" element={<NewEstimate onOpen={(id) => navigate(`/estimates/${id}`)} />} />}
          {!isClient && (
            <Route path="/settings" element={<SettingsLayout isAdmin={isAdmin} />}>
              <Route index element={<Navigate to="rates" replace />} />
              <Route path="rates" element={<RatesView />} />
              {isAdmin && <Route path="variables" element={<VariablesView />} />}
              {isAdmin && <Route path="admin" element={<AdminView />} />}
            </Route>
          )}
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </main>
    </>
  );
}
