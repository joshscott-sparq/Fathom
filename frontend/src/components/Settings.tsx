import { NavLink, Outlet } from "react-router-dom";

export function SettingsLayout({ isAdmin }: { isAdmin: boolean }) {
  const tabClass = ({ isActive }: { isActive: boolean }) =>
    "px-3 py-2 text-[13px] font-medium border-b-2 -mb-px " +
    (isActive ? "border-brand-orange text-ink" : "border-transparent text-muted hover:text-ink");

  return (
    <div>
      <div className="flex items-center gap-1 border-b border-line mb-4">
        <NavLink to="rates" className={tabClass}>Rates</NavLink>
        {isAdmin && <NavLink to="variables" className={tabClass}>Variables</NavLink>}
        {isAdmin && <NavLink to="admin" className={tabClass}>Users & accounts</NavLink>}
      </div>
      <Outlet />
    </div>
  );
}
