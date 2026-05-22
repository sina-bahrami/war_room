import type { DashboardFilterOptions, TenderFilters } from "../lib/types";

interface FilterBarProps {
  filters: TenderFilters;
  onChange: (filters: TenderFilters) => void;
  options: DashboardFilterOptions;
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

export function FilterBar({ filters, onChange, options }: FilterBarProps) {
  return (
    <section className="panel">
      <div className="panel__header">
        <div>
          <h2>Opportunity Filters</h2>
          <p>Filter by source, sector, state, value band, known value, and closing date range.</p>
        </div>
        <button type="button" className="ghost-button" onClick={() => onChange(EMPTY_FILTERS)}>
          Reset
        </button>
      </div>
      <div className="filters">
        <input
          value={filters.query}
          onChange={(event) => onChange({ ...filters, query: event.target.value })}
          placeholder="Search title, description, or agency"
        />
        <select
          value={filters.source}
          onChange={(event) => onChange({ ...filters, source: event.target.value })}
        >
          <option value="">All sources</option>
          {options.sources.map((item) => (
            <option key={item} value={item}>
              {item}
            </option>
          ))}
        </select>
        <select
          value={filters.state}
          onChange={(event) => onChange({ ...filters, state: event.target.value })}
        >
          <option value="">All states</option>
          {options.states.map((item) => (
            <option key={item} value={item}>
              {item}
            </option>
          ))}
        </select>
        <select
          value={filters.sector_primary}
          onChange={(event) => onChange({ ...filters, sector_primary: event.target.value })}
        >
          <option value="">All sectors</option>
          {options.sector_primary.map((item) => (
            <option key={item} value={item}>
              {item}
            </option>
          ))}
        </select>
        <select
          value={filters.status}
          onChange={(event) => onChange({ ...filters, status: event.target.value })}
        >
          <option value="">All statuses</option>
          <option value="open">open</option>
          <option value="closed">closed</option>
          <option value="forecast">forecast</option>
          <option value="archived">archived</option>
        </select>
        <select
          value={filters.view_bucket}
          onChange={(event) => onChange({ ...filters, view_bucket: event.target.value })}
        >
          <option value="">Current tab bucket</option>
          {options.view_buckets.map((item) => (
            <option key={item} value={item}>
              {item}
            </option>
          ))}
        </select>
        <select
          value={filters.value_band}
          onChange={(event) => onChange({ ...filters, value_band: event.target.value })}
        >
          <option value="">All value bands</option>
          {options.value_bands.map((item) => (
            <option key={item} value={item}>
              {item}
            </option>
          ))}
        </select>
        <select
          value={filters.value_known}
          onChange={(event) =>
            onChange({
              ...filters,
              value_known: event.target.value as TenderFilters["value_known"],
            })
          }
        >
          <option value="">Known or unknown value</option>
          <option value="known">Known value only</option>
          <option value="unknown">Unknown value only</option>
        </select>
        <input
          type="date"
          value={filters.closing_from}
          onChange={(event) => onChange({ ...filters, closing_from: event.target.value })}
        />
        <input
          type="date"
          value={filters.closing_to}
          onChange={(event) => onChange({ ...filters, closing_to: event.target.value })}
        />
      </div>
    </section>
  );
}
