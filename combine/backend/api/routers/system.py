from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends
from redis.asyncio import Redis

from api.dependencies import get_analytics_service, get_redis
from api.models.schemas import DashboardSummaryResponse, HealthResponse, SourceHealthResponse
from api.services.analytics import AnalyticsService

router = APIRouter(tags=["system"])


@router.get("/health", response_model=HealthResponse)
async def health(redis: Redis | None = Depends(get_redis)) -> HealthResponse:
    redis_status = "disconnected"
    if redis is not None:
        try:
            await redis.ping()
            redis_status = "connected"
        except Exception:
            redis_status = "degraded"

    return HealthResponse(
        status="ok",
        database="connected",
        redis=redis_status,
        generated_at=datetime.utcnow(),
    )


@router.get("/api/dashboard/summary", response_model=DashboardSummaryResponse)
async def dashboard_summary(
    analytics: AnalyticsService = Depends(get_analytics_service),
) -> DashboardSummaryResponse:
    return await analytics.get_dashboard_summary()


@router.get("/api/sources/health", response_model=list[SourceHealthResponse])
async def source_health(
    analytics: AnalyticsService = Depends(get_analytics_service),
) -> list[SourceHealthResponse]:
    return (await analytics.get_dashboard_summary()).source_health
