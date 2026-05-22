import type { TenderRecord } from "../lib/types";

function formatMoney(value: number | null) {
  if (value == null) return "Unknown";
  return new Intl.NumberFormat("en-AU", {
    style: "currency",
    currency: "AUD",
    maximumFractionDigits: 0,
  }).format(value);
}

function formatDate(value: string | null) {
  return value ? new Date(value).toLocaleDateString() : "TBC";
}

function formatDaysToClose(value: number | null) {
  if (value == null) return "-";
  if (value === 0) return "Today";
  if (value > 0) return `${value}d`;
  return `${Math.abs(value)}d ago`;
}

interface TenderTableProps {
  items: TenderRecord[];
  total: number;
}

export function TenderTable({ items, total }: TenderTableProps) {
  return (
    <section className="panel">
      <div className="panel__header">
        <div>
          <h2>Opportunity Register</h2>
          <p>{total} opportunities matched the current view and filters.</p>
        </div>
      </div>
      <div className="table-wrap">
        <table className="tender-table">
          <thead>
            <tr>
              <th>Opportunity</th>
              <th>Agency</th>
              <th>State</th>
              <th>Sector</th>
              <th>Source</th>
              <th>Status</th>
              <th>Bucket</th>
              <th>Closing</th>
              <th>Days</th>
              <th>Value</th>
              <th>Docs</th>
            </tr>
          </thead>
          <tbody>
            {items.map((item) => (
              <tr key={item.id}>
                <td>
                  <div className="table-title">
                    <a href={item.source_url} target="_blank" rel="noreferrer">
                      {item.title}
                    </a>
                    <span>{item.description || item.summary}</span>
                  </div>
                </td>
                <td>{item.agency || item.buyer_name}</td>
                <td>{item.state}</td>
                <td>{item.sector_primary || item.category}</td>
                <td>{item.source_name || item.source}</td>
                <td>
                  <span className="pill">{item.status}</span>
                </td>
                <td>
                  <span className="pill pill--neutral">{item.view_bucket}</span>
                </td>
                <td>{formatDate(item.closing_at || item.closing_date)}</td>
                <td>{formatDaysToClose(item.days_to_close)}</td>
                <td>{formatMoney(item.estimated_value_aud)}</td>
                <td>
                  {item.documents_url ? (
                    <a href={item.documents_url} target="_blank" rel="noreferrer">
                      Open
                    </a>
                  ) : (
                    "-"
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}
