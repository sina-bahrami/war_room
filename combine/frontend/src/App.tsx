import { useEffect, useState } from "react";
import { BriefcaseBusiness, CalendarClock, Clock3, MapPinned, Wallet } from "lucide-react";
import { DashboardShell } from "./components/DashboardShell";
import { FilterBar } from "./components/FilterBar";
import { OverviewCharts } from "./components/OverviewCharts";
import { SourceHealthTable } from "./components/SourceHealthTable";
import { StatCard } from "./components/StatCard";
import { TenderTable } from "./components/TenderTable";
import { getDashboardSummary, getTenders, triggerIngestion } from "./lib/api";
import type { DashboardSummary, DashboardView, TenderFilters, TenderRecord } from "./lib/types";

function getInitialView(): DashboardView {
  const hash = window.location.hash.replace(/^#\/?/, "");
  if (hash === "upcoming" || hash === "recently_closed" || hash === "sources") {
    return hash;
  }
  return "active";
}

const EMPTY_FILTERS: TenderFilters = {
  query: "",
  source: "",
  status: "",
  state: "",
  sector_primary: "",
  value_band: "",
  closing_from: "",
  closing_to: "",
  value_known: "",
  view_bucket: "",
};

export default function App() {
  const [view, setView] = useState<DashboardView>(getInitialView);
  const [summary, setSummary] = useState<DashboardSummary | null>(null);
  const [filters, setFilters] = useState<TenderFilters>(EMPTY_FILTERS);
  const [tenders, setTenders] = useState<TenderRecord[]>([]);
  const [tenderTotal, setTenderTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [syncing, setSyncing] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const handleHashChange = () => setView(getInitialView());
    window.addEventListener("hashchange", handleHashChange);
    return () => window.removeEventListener("hashchange", handleHashChange);
  }, []);

  useEffect(() => {
    if (!window.location.hash) {
      window.location.hash = "/active";
    }
  }, []);

  useEffect(() => {
    async function loadSummary() {
      setLoading(true);
      setError(null);
      try {
        const dashboard = await getDashboardSummary();
        setSummary(dashboard);
      } catch (loadError) {
        setError(loadError instanceof Error ? loadError.message : "Failed to load dashboard");
      } finally {
        setLoading(false);
      }
    }

    void loadSummary();
  }, []);

  useEffect(() => {
    async function loadTenders() {
      if (view === "sources") {
        return;
      }
      try {
        const response = await getTenders({
          ...filters,
          view_bucket: filters.view_bucket || view,
        });
        setTenders(response.items);
        setTenderTotal(response.total);
      } catch (loadError) {
        setError(loadError instanceof Error ? loadError.message : "Failed to refresh tenders");
      }
    }

    void loadTenders();
  }, [filters, view]);

  async function handleSync() {
    setSyncing(true);
    setError(null);
    try {
      await triggerIngestion();
      const dashboard = await getDashboardSummary();
      setSummary(dashboard);
      if (view !== "sources") {
        const opportunities = await getTenders({
          ...filters,
          view_bucket: filters.view_bucket || view,
        });
        setTenders(opportunities.items);
        setTenderTotal(opportunities.total);
      }
    } catch (syncError) {
      setError(syncError instanceof Error ? syncError.message : "Sync failed");
    } finally {
      setSyncing(false);
    }
  }

  function handleChangeView(nextView: DashboardView) {
    window.location.hash = `/${nextView}`;
    setView(nextView);
  }

  if (loading) {
    return <div className="status-screen">Bootstrapping unified tender dashboard...</div>;
  }

  if (!summary) {
    return <div className="status-screen">No summary data available.</div>;
  }

  const statCards = [
    {
      label: "Total Opportunities",
      value: String(summary.total_opportunities),
      helper: "Unified Australian-market snapshot",
      icon: BriefcaseBusiness,
    },
    {
      label: "Active Bids",
      value: String(summary.active_bids),
      helper: "Currently active opportunities",
      icon: Clock3,
    },
    {
      label: "Upcoming Bids",
      value: String(summary.upcoming_bids),
      helper: "Forecast or soon-to-open opportunities",
      icon: CalendarClock,
    },
    {
      label: "Recently Closed",
      value: String(summary.recently_closed),
      helper: "Recently closed market activity",
      icon: MapPinned,
    },
    {
      label: "Known Value",
      value: String(summary.known_value_records),
      helper: "Records with estimated contract value",
      icon: Wallet,
    },
  ];

  return (
    <DashboardShell
      view={view}
      onChangeView={handleChangeView}
      generatedAt={summary.generated_at}
    >
      {error && <section className="banner banner--error">{error}</section>}

      <section className="stats-grid stats-grid--five">
        {statCards.map(({ label, value, helper, icon: Icon }) => (
          <div key={label} className="stat-card-wrap">
            <div className="stat-card-wrap__icon">
              <Icon size={18} />
            </div>
            <StatCard label={label} value={value} helper={helper} />
          </div>
        ))}
      </section>

      {view !== "sources" && (
        <>
          <FilterBar
            filters={filters}
            onChange={setFilters}
            options={summary.filter_options}
          />
          <OverviewCharts
            sectorData={summary.category_breakdown}
            sourceData={summary.source_breakdown}
            stateData={summary.state_breakdown}
          />
          <TenderTable items={tenders} total={tenderTotal} />
        </>
      )}

      {view === "sources" && (
        <SourceHealthTable items={summary.source_health} isSyncing={syncing} onSync={handleSync} />
      )}
    </DashboardShell>
  );
}
