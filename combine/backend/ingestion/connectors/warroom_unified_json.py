from __future__ import annotations

from common.tender_schema import NormalizedTender
from common.warroom_snapshot import load_warroom_snapshot
from ingestion.common.base import BaseTenderConnector


SOURCE_NAME_MAP = {
    "austender": "AusTender",
    "tenders_net": "Prompcorp Tenders.Net",
}


class WarroomUnifiedJsonConnector(BaseTenderConnector):
    source_id = "warroom_unified_json"
    source_name = "War Room Unified JSON"
    source_url_field = "warroom_json_source_url"
    sample_filename = "warroom_dashboard_data.json"

    async def fetch(self) -> list[NormalizedTender]:
        if not self.source_url:
            return []
        payload = await load_warroom_snapshot(self.source_url)
        opportunities = payload.get("opportunities", [])
        return [
            item
            for item in (self.normalize(record) for record in opportunities if isinstance(record, dict))
            if item is not None
        ]

    def normalize(self, record: dict) -> NormalizedTender | None:
        source = str(record.get("source") or "warroom").strip() or "warroom"
        external_id = str(
            record.get("source_record_id")
            or record.get("id")
            or ""
        ).strip()
        if not external_id:
            return None

        title = str(record.get("title") or "Untitled opportunity").strip()
        description = str(record.get("description") or "").strip()
        agency = str(record.get("agency") or "Unknown agency").strip()
        source_url = str(record.get("source_url") or record.get("documents_url") or "").strip()
        if not source_url:
            source_url = "https://example.invalid"

        metadata = {
            "unified_id": record.get("id"),
            "source": source,
            "source_record_id": record.get("source_record_id"),
            "source_file_dates": record.get("source_file_dates") or [],
            "documents_url": record.get("documents_url"),
            "country": record.get("country"),
            "market_scope": record.get("market_scope"),
            "sector_tags": record.get("sector_tags") or [],
            "service_line_relevance": bool(record.get("service_line_relevance")),
            "view_bucket": record.get("view_bucket") or "active",
            "closing_date": record.get("closing_date"),
            "closing_timezone_text": record.get("closing_timezone_text"),
            "days_to_close": record.get("days_to_close"),
            "closing_soon": bool(record.get("closing_soon")),
            "estimated_value_text": record.get("estimated_value_text"),
            "value_band": record.get("value_band") or "unknown",
            "contact_text": record.get("contact_text"),
            "contact_email": record.get("contact_email"),
            "contact_phone": record.get("contact_phone"),
            "is_invite_only": bool(record.get("is_invite_only")),
            "is_updated_notice": bool(record.get("is_updated_notice")),
            "first_seen_at": record.get("first_seen_at"),
            "last_seen_at": record.get("last_seen_at"),
            "seen_count": record.get("seen_count") or 1,
            "data_quality": record.get("data_quality") or {},
        }

        return NormalizedTender(
            source_id=source,
            source_name=SOURCE_NAME_MAP.get(source, source.replace("_", " ").title()),
            external_id=external_id,
            title=title,
            buyer_name=agency,
            summary=description,
            description=description,
            procurement_stage=str(record.get("view_bucket") or "active"),
            source_url=source_url,
            published_at=record.get("published_at"),
            closes_at=record.get("closing_at"),
            estimated_value=record.get("estimated_value_aud"),
            currency="AUD",
            state=str(record.get("state") or "Unknown"),
            region=str(record.get("country") or "Australia"),
            category=str(record.get("sector_primary") or "other"),
            tags=[str(tag).strip() for tag in record.get("sector_tags", []) if str(tag).strip()],
            status=str(record.get("status") or "unknown"),
            metadata=metadata,
        )
