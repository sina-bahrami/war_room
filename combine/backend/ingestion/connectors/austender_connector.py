from __future__ import annotations

from common.tender_schema import NormalizedTender
from ingestion.common.base import BaseTenderConnector


class AusTenderConnector(BaseTenderConnector):
    source_id = "austender"
    source_name = "AusTender"
    source_url_field = "austender_source_url"
    sample_filename = "austender.json"

    def normalize(self, record: dict) -> NormalizedTender | None:
        raw = record.get("raw") if isinstance(record.get("raw"), dict) else {}
        external_id = str(
            record.get("atm_id")
            or record.get("external_id")
            or record.get("id")
            or record.get("url")
            or ""
        ).strip()
        if not external_id:
            return None
        return NormalizedTender(
            source_id=self.source_id,
            source_name=self.source_name,
            external_id=external_id,
            title=record.get("title") or "Untitled opportunity",
            buyer_name=record.get("agency") or record.get("issuer") or "Commonwealth entity",
            summary=record.get("summary") or "",
            description=record.get("description") or raw.get("description") or record.get("summary", ""),
            procurement_stage=record.get("stage") or record.get("status") or "open",
            source_url=record.get("url") or "https://www.tenders.gov.au",
            published_at=record.get("published_at") or record.get("publish_date"),
            closes_at=record.get("closes_at") or record.get("close_date"),
            estimated_value=record.get("estimated_value") or record.get("value"),
            state=record.get("state") or "National",
            region=record.get("region") or "Australia",
            category=record.get("category") or "Professional Services",
            tags=record.get("tags", []),
            metadata={
                "approach_to_market": record.get("approach_to_market") or record.get("source_type"),
                "division": record.get("division"),
                "raw": raw,
            },
        )
