from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from redis.asyncio import Redis
from api.core.config import settings
from api.core.database import db
from api.dependencies import repository
from api.routers import system, tenders
from api.services.analytics import AnalyticsService


@asynccontextmanager
async def lifespan(_: FastAPI):
    import api.dependencies as dependencies

    await db.connect()
    dependencies.redis_client = Redis.from_url(settings.redis_url, decode_responses=True)
    dependencies.analytics_service = AnalyticsService(repository, dependencies.redis_client)
    yield
    if dependencies.redis_client is not None:
        await dependencies.redis_client.close()
    await db.disconnect()


app = FastAPI(
    title=settings.project_name,
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(system.router)
app.include_router(tenders.router)
