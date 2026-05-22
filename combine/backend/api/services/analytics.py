from __future__ import annotations

from datetime import datetime

from redis.asyncio import Redis

from api.core.config import settings
from api.models.schemas import CountBucket, DashboardFilterOptions, SourceHealthResponse
from api.models.schemas import DashboardSummaryResponse
from api.services.tender_repository import TenderRepository
from common.warroom_snapshot import load_warroom_snapshot, normalize_bucket_mapping


SUMMARY_CACHE_KEY = "combine:dashboard-summary:v1"


class AnalyticsService:
    def __init__(self, repository: TenderRepository, redis: Redis | None) -> None:
        self.repository = repository
        self.redis = redis

    async def get_dashboard_summary(self, use_cache: bool = True) -> DashboardSummaryResponse:
        if use_cache and self.redis is not None:
            cached = await self.redis.get(SUMMARY_CACHE_KEY)
            if cached:
                return DashboardSummaryResponse.model_validate_json(cached)

        if settings.warroom_json_source_url:
            payload = await load_warroom_snapshot(settings.warroom_json_source_url)
            summary = await self._get_unified_dashboard_summary(payload)
        else:
            source_health = await self.repository.list_source_health()
            summary = await self.repository.get_dashboard_summary(source_health)

        if self.redis is not None:
            await self.redis.set(SUMMARY_CACHE_KEY, summary.model_dump_json(), ex=300)
        return summary

    async def invalidate_summary_cache(self) -> None:
        if self.redis is not None:
            await self.redis.delete(SUMMARY_CACHE_KEY)

    async def _get_unified_dashboard_summary(self, payload: dict) -> DashboardSummaryResponse:
        summary_data = payload.get("summary") or {}
        filter_options_data = payload.get("filter_options") or {}
        view_buckets = normalize_bucket_mapping(summary_data.get("view_buckets"))
        source_buckets = normalize_bucket_mapping(summary_data.get("sources"))
        state_buckets = normalize_bucket_mapping(summary_data.get("states"))
        sector_buckets = normalize_bucket_mapping(summary_data.get("sector_primary"))
        status_buckets = normalize_bucket_mapping(summary_data.get("status"))

        closing_items, _ = await self.repository.list_tenders(closing_soon_only=True, limit=8)

        return DashboardSummaryResponse(
            total_tenders=int(summary_data.get("total_records") or 0),
            total_opportunities=int(summary_data.get("total_records") or 0),
            open_opportunities=int(view_buckets.get("active", 0)),
            active_bids=int(view_buckets.get("active", 0)),
            upcoming_bids=int(view_buckets.get("upcoming", 0)),
            recently_closed=int(view_buckets.get("recently_closed", 0)),
            internal_pipeline_items=0,
            closing_this_week=int(summary_data.get("closing_soon_count") or 0),
            closing_soon=int(summary_data.get("closing_soon_count") or 0),
            known_value_records=int(summary_data.get("estimated_value_available_count") or 0),
            average_priority_score=0.0,
            total_estimated_value=0.0,
            stage_breakdown=self._mapping_to_buckets(view_buckets),
            source_breakdown=self._mapping_to_buckets(source_buckets),
            state_breakdown=self._mapping_to_buckets(state_buckets),
            category_breakdown=self._mapping_to_buckets(sector_buckets),
            filter_options=DashboardFilterOptions(
                states=[str(item) for item in filter_options_data.get("states", [])],
                sector_primary=[str(item) for item in filter_options_data.get("sector_primary", [])],
                sources=[str(item) for item in filter_options_data.get("sources", [])],
                view_buckets=[str(item) for item in filter_options_data.get("view_buckets", [])],
                value_bands=[str(item) for item in filter_options_data.get("value_bands", [])],
            ),
            source_health=self._build_unified_source_health(payload.get("source_health") or []),
            closing_soon_items=closing_items,
            featured_pipeline=[],
            generated_at=self._parse_generated_at(payload.get("generated_at")),
        )

    def _mapping_to_buckets(self, mapping: dict[str, int]) -> list[CountBucket]:
        return [
            CountBucket(label=label, value=value)
            for label, value in sorted(mapping.items(), key=lambda item: (-item[1], item[0]))
        ]

    def _build_unified_source_health(self, items: list[dict]) -> list[SourceHealthResponse]:
        health: list[SourceHealthResponse] = []
        for item in items:
            if not isinstance(item, dict):
                continue
            source = str(item.get("source") or "unknown")
            record_count = int(item.get("record_count") or 0)
            health.append(
                SourceHealthResponse(
                    source_id=source,
                    source_name=source.replace("_", " ").title(),
                    status="loaded",
                    records_seen=record_count,
                    records_upserted=record_count,
                    record_count=record_count,
                    active_count=int(item.get("active_count") or 0),
                    upcoming_count=int(item.get("upcoming_count") or 0),
                    recently_closed_count=int(item.get("recently_closed_count") or 0),
                    estimated_value_available_count=int(item.get("estimated_value_available_count") or 0),
                    first_snapshot_date=item.get("first_snapshot_date"),
                    last_snapshot_date=item.get("last_snapshot_date"),
                    message="Loaded from unified war room JSON snapshot",
                )
            )
        return health

    def _parse_generated_at(self, value: str | None) -> datetime:
        if not value:
            return datetime.utcnow()
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return datetime.utcnow()
