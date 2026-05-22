from __future__ import annotations

import asyncio
from datetime import datetime, timezone

from redis.asyncio import Redis

from api.core.config import settings
from api.core.database import db
from api.services.analytics import SUMMARY_CACHE_KEY
from api.services.tender_repository import TenderRepository
from common.tender_schema import SourceRunRecord
from ingestion.connectors import build_connectors


async def run_connectors_once(target_source: str | None = None) -> list[str]:
    manage_db_lifecycle = db.pool is None
    if manage_db_lifecycle:
        await db.connect()
    redis = Redis.from_url(settings.redis_url, decode_responses=True)
    repository = TenderRepository()
    connectors = build_connectors(settings)
    triggered_sources: list[str] = []

    try:
        for connector in connectors:
            if target_source and connector.source_id != target_source:
                continue
            triggered_sources.append(connector.source_id)
            started_at = datetime.now(timezone.utc)
            try:
                tenders = await connector.fetch()
                if settings.warroom_json_source_url and connector.source_id == "warroom_unified_json":
                    upserted = await repository.replace_all_tenders(tenders)
                else:
                    upserted = await repository.upsert_tenders(tenders)
                await repository.record_source_run(
                    SourceRunRecord(
                        source_id=connector.source_id,
                        source_name=connector.source_name,
                        status="success",
                        records_seen=len(tenders),
                        records_upserted=upserted,
                        started_at=started_at,
                        finished_at=datetime.now(timezone.utc),
                        message=f"Ingested {upserted} records",
                    )
                )
            except Exception as exc:
                await repository.record_source_run(
                    SourceRunRecord(
                        source_id=connector.source_id,
                        source_name=connector.source_name,
                        status="failed",
                        records_seen=0,
                        records_upserted=0,
                        started_at=started_at,
                        finished_at=datetime.now(timezone.utc),
                        message=str(exc),
                    )
                )
        await redis.delete(SUMMARY_CACHE_KEY)
        return triggered_sources
    finally:
        await redis.close()
        if manage_db_lifecycle:
            await db.disconnect()


async def run_forever() -> None:
    while True:
        await run_connectors_once()
        await asyncio.sleep(settings.ingestion_interval_seconds)
