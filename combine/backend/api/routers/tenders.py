from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query

from api.dependencies import (
    get_analytics_service,
    get_repository,
    require_admin_user,
    require_authenticated_user,
)
from api.models.schemas import AuthenticatedUserResponse, IngestionRunResponse, TenderListResponse, TenderResponse
from api.services.analytics import AnalyticsService
from api.services.tender_repository import TenderRepository
from ingestion.common.service import run_connectors_once

router = APIRouter(prefix="/api/tenders", tags=["tenders"])


@router.get("", response_model=TenderListResponse)
async def list_tenders(
    query: str = Query(default="", max_length=120),
    source: str = Query(default="", max_length=60),
    stage: str = Query(default="", max_length=60),
    status: str = Query(default="", max_length=60),
    state: str = Query(default="", max_length=60),
    category: str = Query(default="", max_length=60),
    sector_primary: str = Query(default="", max_length=80),
    view_bucket: str = Query(default="", max_length=60),
    value_band: str = Query(default="", max_length=60),
    closing_from: str = Query(default="", max_length=20),
    closing_to: str = Query(default="", max_length=20),
    value_known: bool | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    internal_only: bool | None = Query(default=None),
    repository: TenderRepository = Depends(get_repository),
    _: AuthenticatedUserResponse = Depends(require_authenticated_user),
) -> TenderListResponse:
    items, total = await repository.list_tenders(
        query=query,
        source=source,
        stage=stage,
        status=status,
        state=state,
        category=category,
        sector_primary=sector_primary,
        view_bucket=view_bucket,
        value_band=value_band,
        closing_from=closing_from,
        closing_to=closing_to,
        value_known=value_known,
        limit=limit,
        offset=offset,
        internal_only=internal_only,
    )
    return TenderListResponse(items=items, total=total)


@router.get("/{tender_id}", response_model=TenderResponse)
async def get_tender(
    tender_id: str,
    repository: TenderRepository = Depends(get_repository),
    _: AuthenticatedUserResponse = Depends(require_authenticated_user),
) -> TenderResponse:
    tender = await repository.get_tender(tender_id)
    if not tender:
        raise HTTPException(status_code=404, detail="Tender not found")
    return tender


@router.post("/admin/run-ingestion", response_model=IngestionRunResponse)
async def run_ingestion(
    source: str = Query(default=""),
    analytics: AnalyticsService = Depends(get_analytics_service),
    _: AuthenticatedUserResponse = Depends(require_admin_user),
) -> IngestionRunResponse:
    triggered = await run_connectors_once(target_source=source or None)
    await analytics.invalidate_summary_cache()
    return IngestionRunResponse(
        started=True,
        triggered_sources=triggered,
        message="Ingestion cycle completed",
    )
