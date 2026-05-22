from __future__ import annotations

from redis.asyncio import Redis

from api.services.analytics import AnalyticsService
from api.services.tender_repository import TenderRepository

repository = TenderRepository()
redis_client: Redis | None = None
analytics_service: AnalyticsService | None = None


def get_repository() -> TenderRepository:
    return repository


def get_redis() -> Redis | None:
    return redis_client


def get_analytics_service() -> AnalyticsService:
    assert analytics_service is not None
    return analytics_service
