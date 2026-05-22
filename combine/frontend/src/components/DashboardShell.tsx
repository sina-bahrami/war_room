import type { ReactNode } from "react";
import { Activity, Building2, CalendarClock, CheckCheck, DatabaseZap } from "lucide-react";
import type { DashboardView } from "../lib/types";

const NAV_ITEMS: Array<{ key: DashboardView; label: string; icon: typeof Activity }> = [
  { key: "active", label: "Active Bids", icon: Activity },
  { key: "upcoming", label: "Upcoming Bids", icon: CalendarClock },
  { key: "recently_closed", label: "Recently Closed", icon: CheckCheck },
  { key: "sources", label: "Sources", icon: DatabaseZap },
];

interface DashboardShellProps {
  view: DashboardView;
  onChangeView: (view: DashboardView) => void;
  generatedAt: string | null;
  children: ReactNode;
}

export function DashboardShell({
  view,
  onChangeView,
  generatedAt,
  children,
}: DashboardShellProps) {
  return (
    <div className="app-shell">
      <header className="hero">
        <div>
          <p className="hero__eyebrow">Combined Platform</p>
          <h1>Prompcorp Tender Intelligence</h1>
          <p className="hero__copy">
            Unified Australian-market opportunity monitoring with brief-aligned views
            for active bids, upcoming bids, recently closed work, and source-health tracking.
          </p>
        </div>
        <div className="hero__stamp">
          <Building2 size={18} />
          <div>
            <div className="hero__stamp-label">Last refresh</div>
            <div className="hero__stamp-value">
              {generatedAt ? new Date(generatedAt).toLocaleString() : "Waiting for ingest"}
            </div>
          </div>
        </div>
      </header>

      <nav className="tab-nav">
        {NAV_ITEMS.map(({ key, label, icon: Icon }) => (
          <button
            key={key}
            type="button"
            className={key === view ? "tab-nav__item tab-nav__item--active" : "tab-nav__item"}
            onClick={() => onChangeView(key)}
          >
            <Icon size={16} />
            {label}
          </button>
        ))}
      </nav>

      <main className="dashboard-grid">{children}</main>
    </div>
  );
}
