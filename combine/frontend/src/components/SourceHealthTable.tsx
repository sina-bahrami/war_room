import type { SourceHealth } from "../lib/types";

interface SourceHealthTableProps {
  items: SourceHealth[];
  isSyncing: boolean;
  onSync: () => void;
  canSync: boolean;
}

export function SourceHealthTable({ items, isSyncing, onSync, canSync }: SourceHealthTableProps) {
  return (
    <section className="panel">
      <div className="panel__header">
        <div>
          <h2>Source Health and Snapshot Coverage</h2>
          <p>Top-level source health from the unified war room JSON snapshot.</p>
        </div>
        {canSync ? (
          <button type="button" className="primary-button" onClick={onSync} disabled={isSyncing}>
            {isSyncing ? "Syncing..." : "Run Ingestion"}
          </button>
        ) : (
          <span className="source-health-note">Admin access is required to run ingestion.</span>
        )}
      </div>
      <div className="table-wrap">
        <table className="tender-table">
          <thead>
            <tr>
              <th>Source</th>
              <th>Status</th>
              <th>Total</th>
              <th>Active</th>
              <th>Upcoming</th>
              <th>Recently Closed</th>
              <th>Known Value</th>
              <th>First Snapshot</th>
              <th>Last Snapshot</th>
            </tr>
          </thead>
          <tbody>
            {items.map((item) => (
              <tr key={item.source_id}>
                <td>{item.source_name}</td>
                <td>
                  <span className={item.status === "loaded" || item.status === "success" ? "pill pill--success" : "pill pill--danger"}>
                    {item.status}
                  </span>
                </td>
                <td>{item.record_count || item.records_seen}</td>
                <td>{item.active_count}</td>
                <td>{item.upcoming_count}</td>
                <td>{item.recently_closed_count}</td>
                <td>{item.estimated_value_available_count}</td>
                <td>{item.first_snapshot_date ?? "-"}</td>
                <td>{item.last_snapshot_date ?? "-"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}
