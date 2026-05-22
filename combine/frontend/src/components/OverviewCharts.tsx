import {
  Bar,
  BarChart,
  Cell,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import type { CountBucket } from "../lib/types";

const PIE_COLORS = ["#5ea3ff", "#efb45d", "#54c4a8", "#ef6b63", "#8fc97d", "#cb8df7"];

interface OverviewChartsProps {
  sectorData: CountBucket[];
  sourceData: CountBucket[];
  stateData: CountBucket[];
}

export function OverviewCharts({ sectorData, sourceData, stateData }: OverviewChartsProps) {
  return (
    <div className="chart-grid">
      <section className="panel chart-panel">
        <div className="panel__header">
          <div>
            <h2>Sector Distribution</h2>
            <p>Primary sector mix across the unified opportunity feed.</p>
          </div>
        </div>
        <ResponsiveContainer width="100%" height={280}>
          <BarChart data={sectorData}>
            <XAxis dataKey="label" stroke="#8da5b8" />
            <YAxis stroke="#8da5b8" />
            <Tooltip />
            <Bar dataKey="value" fill="#5ea3ff" radius={[8, 8, 0, 0]} />
          </BarChart>
        </ResponsiveContainer>
      </section>

      <section className="panel chart-panel">
        <div className="panel__header">
          <div>
            <h2>Source Mix</h2>
            <p>Where the unified feed is sourcing opportunity records from.</p>
          </div>
        </div>
        <ResponsiveContainer width="100%" height={280}>
          <PieChart>
            <Pie data={sourceData} dataKey="value" nameKey="label" innerRadius={55} outerRadius={100}>
              {sourceData.map((entry, index) => (
                <Cell key={entry.label} fill={PIE_COLORS[index % PIE_COLORS.length]} />
              ))}
            </Pie>
            <Tooltip />
          </PieChart>
        </ResponsiveContainer>
      </section>

      <section className="panel chart-panel">
        <div className="panel__header">
          <div>
            <h2>State Concentration</h2>
            <p>Regional concentration across states and territories.</p>
          </div>
        </div>
        <ResponsiveContainer width="100%" height={280}>
          <BarChart data={stateData} layout="vertical" margin={{ left: 10, right: 10 }}>
            <XAxis type="number" stroke="#8da5b8" />
            <YAxis type="category" dataKey="label" stroke="#8da5b8" width={90} />
            <Tooltip />
            <Bar dataKey="value" fill="#54c4a8" radius={[0, 8, 8, 0]} />
          </BarChart>
        </ResponsiveContainer>
      </section>
    </div>
  );
}
