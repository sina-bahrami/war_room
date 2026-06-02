from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class CountBucket(BaseModel):
    label: str
    value: int


class AuthenticatedUserResponse(BaseModel):
    id: str
    name: str
    email: str
    login_name: str | None = None
    is_admin: bool
    created_at: datetime


class LoginRequest(BaseModel):
    identifier: str = Field(min_length=1, max_length=255)
    password: str = Field(min_length=1, max_length=255)


class RegisterRequest(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    email: str = Field(min_length=3, max_length=255)
    password: str = Field(min_length=4, max_length=255)


class AuthSessionResponse(BaseModel):
    authenticated: bool
    user: AuthenticatedUserResponse


class TenderResponse(BaseModel):
    id: str
    source: str = ""
    source_id: str
    source_name: str
    external_id: str
    source_record_id: str = ""
    title: str
    agency: str = ""
    buyer_name: str
    summary: str
    description: str
    procurement_stage: str
    view_bucket: str = ""
    source_url: str
    documents_url: str | None = None
    published_at: datetime | None = None
    closing_at: datetime | None = None
    closes_at: datetime | None = None
    closing_date: str | None = None
    days_to_close: int | None = None
    closing_soon: bool = False
    estimated_value_aud: float | None = None
    estimated_value: float | None = None
    estimated_value_text: str | None = None
    value_band: str | None = None
    currency: str
    state: str
    region: str
    sector_primary: str = ""
    category: str
    sector_tags: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    service_line_relevance: bool = False
    status: str
    priority_score: float
    is_internal: bool
    contact_email: str | None = None
    is_invite_only: bool = False
    is_updated_notice: bool = False
    first_seen_at: datetime | None = None
    last_seen_at: datetime | None = None
    seen_count: int = 0
    metadata: dict[str, Any] = Field(default_factory=dict)
    updated_at: datetime


class TenderListResponse(BaseModel):
    items: list[TenderResponse]
    total: int


class SourceHealthResponse(BaseModel):
    source_id: str
    source_name: str
    status: str
    records_seen: int
    records_upserted: int
    record_count: int = 0
    active_count: int = 0
    upcoming_count: int = 0
    recently_closed_count: int = 0
    estimated_value_available_count: int = 0
    first_snapshot_date: str | None = None
    last_snapshot_date: str | None = None
    started_at: datetime | None = None
    finished_at: datetime | None = None
    message: str | None = None


class DashboardFilterOptions(BaseModel):
    states: list[str] = Field(default_factory=list)
    sector_primary: list[str] = Field(default_factory=list)
    sources: list[str] = Field(default_factory=list)
    view_buckets: list[str] = Field(default_factory=list)
    value_bands: list[str] = Field(default_factory=list)


class DashboardSummaryResponse(BaseModel):
    total_tenders: int
    total_opportunities: int
    open_opportunities: int
    active_bids: int
    upcoming_bids: int
    recently_closed: int
    internal_pipeline_items: int
    closing_this_week: int
    closing_soon: int
    known_value_records: int
    average_priority_score: float
    total_estimated_value: float
    stage_breakdown: list[CountBucket]
    source_breakdown: list[CountBucket]
    state_breakdown: list[CountBucket]
    category_breakdown: list[CountBucket]
    filter_options: DashboardFilterOptions = Field(default_factory=DashboardFilterOptions)
    source_health: list[SourceHealthResponse]
    closing_soon_items: list[TenderResponse]
    featured_pipeline: list[TenderResponse]
    generated_at: datetime


class IngestionRunResponse(BaseModel):
    started: bool
    triggered_sources: list[str]
    message: str


class HealthResponse(BaseModel):
    status: str
    database: str
    redis: str
    generated_at: datetime
