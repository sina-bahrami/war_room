export type DashboardView = "active" | "upcoming" | "recently_closed" | "sources";

export interface CountBucket {
  label: string;
  value: number;
}

export interface TenderRecord {
  id: string;
  source: string;
  source_id: string;
  source_name: string;
  external_id: string;
  source_record_id: string;
  title: string;
  agency: string;
  buyer_name: string;
  summary: string;
  description: string;
  procurement_stage: string;
  view_bucket: string;
  source_url: string;
  documents_url: string | null;
  published_at: string | null;
  closing_at: string | null;
  closes_at: string | null;
  closing_date: string | null;
  days_to_close: number | null;
  closing_soon: boolean;
  estimated_value_aud: number | null;
  estimated_value: number | null;
  estimated_value_text: string | null;
  value_band: string | null;
  currency: string;
  state: string;
  region: string;
  sector_primary: string;
  category: string;
  sector_tags: string[];
  tags: string[];
  service_line_relevance: boolean;
  status: string;
  priority_score: number;
  is_internal: boolean;
  contact_email: string | null;
  is_invite_only: boolean;
  is_updated_notice: boolean;
  first_seen_at: string | null;
  last_seen_at: string | null;
  seen_count: number;
  metadata: Record<string, unknown>;
  updated_at: string;
}

export interface TenderListResponse {
  items: TenderRecord[];
  total: number;
}

export interface SourceHealth {
  source_id: string;
  source_name: string;
  status: string;
  records_seen: number;
  records_upserted: number;
  record_count: number;
  active_count: number;
  upcoming_count: number;
  recently_closed_count: number;
  estimated_value_available_count: number;
  first_snapshot_date: string | null;
  last_snapshot_date: string | null;
  started_at: string | null;
  finished_at: string | null;
  message: string | null;
}

export interface DashboardFilterOptions {
  states: string[];
  sector_primary: string[];
  sources: string[];
  view_buckets: string[];
  value_bands: string[];
}

export interface DashboardSummary {
  total_tenders: number;
  total_opportunities: number;
  open_opportunities: number;
  active_bids: number;
  upcoming_bids: number;
  recently_closed: number;
  internal_pipeline_items: number;
  closing_this_week: number;
  closing_soon: number;
  known_value_records: number;
  average_priority_score: number;
  total_estimated_value: number;
  stage_breakdown: CountBucket[];
  source_breakdown: CountBucket[];
  state_breakdown: CountBucket[];
  category_breakdown: CountBucket[];
  filter_options: DashboardFilterOptions;
  source_health: SourceHealth[];
  closing_soon_items: TenderRecord[];
  featured_pipeline: TenderRecord[];
  generated_at: string;
}

export interface TenderFilters {
  query: string;
  source: string;
  status: string;
  state: string;
  sector_primary: string;
  value_band: string;
  closing_from: string;
  closing_to: string;
  value_known: "" | "known" | "unknown";
  view_bucket: string;
}
