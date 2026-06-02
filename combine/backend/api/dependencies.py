from __future__ import annotations

from fastapi import HTTPException, Request, status
from redis.asyncio import Redis

from api.models.schemas import AuthenticatedUserResponse
from api.services.analytics import AnalyticsService
from api.services.auth import AuthService
from api.services.tender_repository import TenderRepository

repository = TenderRepository()
auth_service = AuthService()
redis_client: Redis | None = None
analytics_service: AnalyticsService | None = None
SESSION_USER_ID_KEY = "user_id"


def get_repository() -> TenderRepository:
    return repository


def get_auth_service() -> AuthService:
    return auth_service


def get_redis() -> Redis | None:
    return redis_client


def get_analytics_service() -> AnalyticsService:
    assert analytics_service is not None
    return analytics_service


async def get_current_user(request: Request) -> AuthenticatedUserResponse | None:
    user_id = request.session.get(SESSION_USER_ID_KEY)
    if not user_id:
        return None
    user = await auth_service.get_user_by_id(str(user_id))
    if user is None:
        request.session.clear()
        return None
    return user


async def require_authenticated_user(
    request: Request,
) -> AuthenticatedUserResponse:
    user = await get_current_user(request)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required.",
        )
    return user


async def require_admin_user(request: Request) -> AuthenticatedUserResponse:
    user = await require_authenticated_user(request)
    if not user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Administrator access required.",
        )
    return user
