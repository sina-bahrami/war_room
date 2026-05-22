from __future__ import annotations

import json
from datetime import datetime
from typing import Any

import asyncpg

from api.core.database import db
from api.models.schemas import CountBucket, DashboardFilterOptions, DashboardSummaryResponse, SourceHealthResponse, TenderResponse
from common.tender_schema import NormalizedTender, SourceRunRecord


class TenderRepository:
    def _build_tender_rows(self, tenders: list[NormalizedTender]) -> list[tuple[Any, ...]]:
        return [
            (
                tender.source_id,
                tender.source_name,
                tender.external_id,
                tender.title,
                tender.buyer_name,
                tender.summary,
                tender.description,
                tender.procurement_stage,
                tender.source_url,
                tender.published_at,
                tender.closes_at,
                tender.estimated_value,
                tender.currency,
                tender.state,
                tender.region,
                tender.category,
                tender.tags,
                tender.status,
                tender.priority_score,
                tender.is_internal,
                json.dumps(tender.metadata),
                tender.last_ingested_at,
            )
            for tender in tenders
        ]

    async def upsert_tenders(self, tenders: list[NormalizedTender]) -> int:
        if not tenders:
            return 0
        assert db.pool is not None
        query = """
        INSERT INTO tenders (
          source_id, source_name, external_id, title, buyer_name, summary, description,
          procurement_stage, source_url, published_at, closes_at, estimated_value,
          currency, state, region, category, tags, status, priority_score,
          is_internal, metadata, last_ingested_at
        )
        VALUES (
          $1, $2, $3, $4, $5, $6, $7,
          $8, $9, $10, $11, $12,
          $13, $14, $15, $16, $17, $18, $19,
          $20, $21::jsonb, $22
        )
        ON CONFLICT (source_id, external_id) DO UPDATE SET
          source_name = EXCLUDED.source_name,
          title = EXCLUDED.title,
          buyer_name = EXCLUDED.buyer_name,
          summary = EXCLUDED.summary,
          description = EXCLUDED.description,
          procurement_stage = EXCLUDED.procurement_stage,
          source_url = EXCLUDED.source_url,
          published_at = EXCLUDED.published_at,
          closes_at = EXCLUDED.closes_at,
          estimated_value = EXCLUDED.estimated_value,
          currency = EXCLUDED.currency,
          state = EXCLUDED.state,
          region = EXCLUDED.region,
          category = EXCLUDED.category,
          tags = EXCLUDED.tags,
          status = EXCLUDED.status,
          priority_score = EXCLUDED.priority_score,
          is_internal = EXCLUDED.is_internal,
          metadata = EXCLUDED.metadata,
          last_ingested_at = EXCLUDED.last_ingested_at,
          updated_at = NOW()
        """
        rows = self._build_tender_rows(tenders)
        async with db.pool.acquire() as conn:
            async with conn.transaction():
                await conn.executemany(query, rows)
        return len(rows)

    async def replace_all_tenders(self, tenders: list[NormalizedTender]) -> int:
        assert db.pool is not None
        insert_query = """
        INSERT INTO tenders (
          source_id, source_name, external_id, title, buyer_name, summary, description,
          procurement_stage, source_url, published_at, closes_at, estimated_value,
          currency, state, region, category, tags, status, priority_score,
          is_internal, metadata, last_ingested_at
        )
        VALUES (
          $1, $2, $3, $4, $5, $6, $7,
          $8, $9, $10, $11, $12,
          $13, $14, $15, $16, $17, $18, $19,
          $20, $21::jsonb, $22
        )
        """
        rows = self._build_tender_rows(tenders)
        async with db.pool.acquire() as conn:
            async with conn.transaction():
                await conn.execute("TRUNCATE TABLE tenders")
                if rows:
                    await conn.executemany(insert_query, rows)
        return len(rows)

    async def record_source_run(self, record: SourceRunRecord) -> None:
        assert db.pool is not None
        query = """
        INSERT INTO source_runs (
          source_id, source_name, status, records_seen, records_upserted, started_at, finished_at, message
        )
        VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
        """
        async with db.pool.acquire() as conn:
            await conn.execute(
                query,
                record.source_id,
                record.source_name,
                record.status,
                record.records_seen,
                record.records_upserted,
                record.started_at,
                record.finished_at,
                record.message,
            )

    async def list_tenders(
        self,
        *,
        query: str = "",
        source: str = "",
        stage: str = "",
        status: str = "",
        state: str = "",
        category: str = "",
        sector_primary: str = "",
        view_bucket: str = "",
        value_band: str = "",
        closing_from: str = "",
        closing_to: str = "",
        value_known: bool | None = None,
        closing_soon_only: bool | None = None,
        limit: int = 50,
        offset: int = 0,
        internal_only: bool | None = None,
    ) -> tuple[list[TenderResponse], int]:
        assert db.pool is not None
        predicates = []
        params: list[Any] = []

        if query:
            params.append(f"%{query.lower()}%")
            idx = len(params)
            predicates.append(f"(lower(title) LIKE ${idx} OR lower(summary) LIKE ${idx} OR lower(buyer_name) LIKE ${idx})")
        if source:
            params.append(source)
            predicates.append(f"source_id = ${len(params)}")
        if stage:
            params.append(stage)
            predicates.append(f"procurement_stage = ${len(params)}")
        if view_bucket:
            params.append(view_bucket)
            predicates.append(f"(procurement_stage = ${len(params)} OR metadata->>'view_bucket' = ${len(params)})")
        if status:
            params.append(status)
            predicates.append(f"status = ${len(params)}")
        if state:
            params.append(state)
            predicates.append(f"state = ${len(params)}")
        if category:
            params.append(category)
            predicates.append(f"category = ${len(params)}")
        if sector_primary:
            params.append(sector_primary)
            predicates.append(f"category = ${len(params)}")
        if value_band:
            params.append(value_band)
            predicates.append(
                f"COALESCE(metadata->>'value_band', CASE WHEN estimated_value IS NULL THEN 'unknown' ELSE '' END) = ${len(params)}"
            )
        if closing_from:
            params.append(closing_from)
            predicates.append(f"closes_at::date >= ${len(params)}::date")
        if closing_to:
            params.append(closing_to)
            predicates.append(f"closes_at::date <= ${len(params)}::date")
        if value_known is not None:
            predicates.append("estimated_value IS NOT NULL" if value_known else "estimated_value IS NULL")
        if closing_soon_only is not None:
            params.append(str(closing_soon_only).lower())
            predicates.append(f"COALESCE(metadata->>'closing_soon', 'false') = ${len(params)}")
        if internal_only is not None:
            params.append(internal_only)
            predicates.append(f"is_internal = ${len(params)}")

        where_clause = f"WHERE {' AND '.join(predicates)}" if predicates else ""
        limit_index = len(params) + 1
        offset_index = len(params) + 2

        count_query = f"SELECT COUNT(*) FROM tenders {where_clause}"
        data_query = f"""
        SELECT *
        FROM tenders
        {where_clause}
        ORDER BY priority_score DESC, closes_at NULLS LAST, updated_at DESC
        LIMIT ${limit_index}
        OFFSET ${offset_index}
        """

        async with db.pool.acquire() as conn:
            total = await conn.fetchval(count_query, *params)
            rows = await conn.fetch(data_query, *params, limit, offset)

        return [self._row_to_tender(row) for row in rows], int(total or 0)

    async def get_tender(self, tender_id: str) -> TenderResponse | None:
        assert db.pool is not None
        async with db.pool.acquire() as conn:
            row = await conn.fetchrow("SELECT * FROM tenders WHERE id = $1", tender_id)
        return self._row_to_tender(row) if row else None

    async def get_dashboard_summary(self, source_health: list[SourceHealthResponse]) -> DashboardSummaryResponse:
        assert db.pool is not None
        async with db.pool.acquire() as conn:
            totals = await conn.fetchrow(
                """
                SELECT
                  COUNT(*) AS total_tenders,
                  COUNT(*) FILTER (WHERE procurement_stage IN ('open', 'qualification', 'proposal')) AS open_opportunities,
                  COUNT(*) FILTER (WHERE is_internal) AS internal_pipeline_items,
                  COUNT(*) FILTER (
                    WHERE closes_at IS NOT NULL
                      AND closes_at <= NOW() + INTERVAL '7 days'
                      AND closes_at >= NOW()
                  ) AS closing_this_week,
                  COALESCE(AVG(priority_score), 0) AS average_priority_score,
                  COALESCE(SUM(estimated_value), 0) AS total_estimated_value
                FROM tenders
                """
            )

            closing_soon_rows = await conn.fetch(
                """
                SELECT *
                FROM tenders
                WHERE closes_at IS NOT NULL
                  AND closes_at >= NOW()
                ORDER BY closes_at ASC, priority_score DESC
                LIMIT 8
                """
            )
            pipeline_rows = await conn.fetch(
                """
                SELECT *
                FROM tenders
                WHERE is_internal = TRUE
                ORDER BY priority_score DESC, updated_at DESC
                LIMIT 8
                """
            )

            return DashboardSummaryResponse(
                total_tenders=int(totals["total_tenders"] or 0),
                total_opportunities=int(totals["total_tenders"] or 0),
                open_opportunities=int(totals["open_opportunities"] or 0),
                active_bids=int(totals["open_opportunities"] or 0),
                upcoming_bids=0,
                recently_closed=0,
                internal_pipeline_items=int(totals["internal_pipeline_items"] or 0),
                closing_this_week=int(totals["closing_this_week"] or 0),
                closing_soon=int(totals["closing_this_week"] or 0),
                known_value_records=0,
                average_priority_score=round(float(totals["average_priority_score"] or 0), 2),
                total_estimated_value=float(totals["total_estimated_value"] or 0),
                stage_breakdown=await self._fetch_bucketed(conn, "procurement_stage"),
                source_breakdown=await self._fetch_bucketed(conn, "source_id"),
                state_breakdown=await self._fetch_bucketed(conn, "state"),
                category_breakdown=await self._fetch_bucketed(conn, "category"),
                filter_options=DashboardFilterOptions(),
                source_health=source_health,
                closing_soon_items=[self._row_to_tender(row) for row in closing_soon_rows],
                featured_pipeline=[self._row_to_tender(row) for row in pipeline_rows],
                generated_at=datetime.utcnow(),
            )

    async def list_source_health(self) -> list[SourceHealthResponse]:
        assert db.pool is not None
        query = """
        SELECT DISTINCT ON (source_id)
          source_id, source_name, status, records_seen, records_upserted, started_at, finished_at, message
        FROM source_runs
        ORDER BY source_id, started_at DESC
        """
        async with db.pool.acquire() as conn:
            rows = await conn.fetch(query)
        return [
            SourceHealthResponse(
                source_id=row["source_id"],
                source_name=row["source_name"],
                status=row["status"],
                records_seen=row["records_seen"],
                records_upserted=row["records_upserted"],
                started_at=row["started_at"],
                finished_at=row["finished_at"],
                message=row["message"],
            )
            for row in rows
        ]

    async def _fetch_bucketed(self, conn: asyncpg.Connection, column: str) -> list[CountBucket]:
        rows = await conn.fetch(
            f"""
            SELECT {column} AS label, COUNT(*) AS value
            FROM tenders
            GROUP BY {column}
            ORDER BY value DESC, label ASC
            LIMIT 8
            """
        )
        return [CountBucket(label=row["label"], value=int(row["value"])) for row in rows]

    def _row_to_tender(self, row: asyncpg.Record) -> TenderResponse:
        metadata = row["metadata"]
        if isinstance(metadata, str):
            metadata = json.loads(metadata)
        return TenderResponse(
            id=str(row["id"]),
            source=row["source_id"],
            source_id=row["source_id"],
            source_name=row["source_name"],
            external_id=row["external_id"],
            source_record_id=str(metadata.get("source_record_id") or row["external_id"]),
            title=row["title"],
            agency=row["buyer_name"],
            buyer_name=row["buyer_name"],
            summary=row["summary"],
            description=row["description"],
            procurement_stage=row["procurement_stage"],
            view_bucket=str(metadata.get("view_bucket") or row["procurement_stage"]),
            source_url=row["source_url"],
            documents_url=metadata.get("documents_url"),
            published_at=row["published_at"],
            closing_at=row["closes_at"],
            closes_at=row["closes_at"],
            closing_date=str(metadata.get("closing_date") or "") or None,
            days_to_close=metadata.get("days_to_close"),
            closing_soon=bool(metadata.get("closing_soon", False)),
            estimated_value_aud=float(row["estimated_value"]) if row["estimated_value"] is not None else None,
            estimated_value=float(row["estimated_value"]) if row["estimated_value"] is not None else None,
            estimated_value_text=metadata.get("estimated_value_text"),
            value_band=str(metadata.get("value_band") or ("unknown" if row["estimated_value"] is None else "")) or None,
            currency=row["currency"],
            state=row["state"],
            region=row["region"],
            sector_primary=row["category"],
            category=row["category"],
            sector_tags=list(metadata.get("sector_tags") or row["tags"] or []),
            tags=list(row["tags"] or []),
            service_line_relevance=bool(metadata.get("service_line_relevance", False)),
            status=row["status"],
            priority_score=float(row["priority_score"] or 0),
            is_internal=bool(row["is_internal"]),
            contact_email=metadata.get("contact_email"),
            is_invite_only=bool(metadata.get("is_invite_only", False)),
            is_updated_notice=bool(metadata.get("is_updated_notice", False)),
            first_seen_at=metadata.get("first_seen_at"),
            last_seen_at=metadata.get("last_seen_at"),
            seen_count=int(metadata.get("seen_count") or 0),
            metadata=metadata or {},
            updated_at=row["updated_at"],
        )
