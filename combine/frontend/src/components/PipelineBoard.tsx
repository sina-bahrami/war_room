import type { TenderRecord } from "../lib/types";

const STAGES = ["qualification", "proposal", "submitted", "award-watch"];

function formatMoney(value: number | null, currency: string) {
  if (value == null) return "Undisclosed";
  return new Intl.NumberFormat("en-AU", {
    style: "currency",
    currency,
    maximumFractionDigits: 0,
  }).format(value);
}

interface PipelineBoardProps {
  items: TenderRecord[];
}

export function PipelineBoard({ items }: PipelineBoardProps) {
  const groups = STAGES.map((stage) => ({
    stage,
    items: items.filter((item) => item.procurement_stage === stage),
  }));

  return (
    <section className="pipeline-board">
      {groups.map((group) => (
        <div key={group.stage} className="pipeline-column">
          <div className="pipeline-column__header">
            <h3>{group.stage}</h3>
            <span>{group.items.length}</span>
          </div>
          <div className="pipeline-column__body">
            {group.items.map((item) => (
              <article key={item.id} className="pipeline-card">
                <div className="pipeline-card__meta">
                  <span>{item.state}</span>
                  <span>{item.priority_score.toFixed(0)}</span>
                </div>
                <h4>{item.title}</h4>
                <p>{item.summary}</p>
                <dl>
                  <div>
                    <dt>Client</dt>
                    <dd>{item.buyer_name}</dd>
                  </div>
                  <div>
                    <dt>Value</dt>
                    <dd>{formatMoney(item.estimated_value, item.currency)}</dd>
                  </div>
                  <div>
                    <dt>Bid Lead</dt>
                    <dd>{String(item.metadata.bid_lead ?? "Unassigned")}</dd>
                  </div>
                </dl>
              </article>
            ))}
          </div>
        </div>
      ))}
    </section>
  );
}
