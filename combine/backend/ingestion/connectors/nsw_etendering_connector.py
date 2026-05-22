from __future__ import annotations

from common.tender_schema import NormalizedTender
from ingestion.common.base import BaseTenderConnector


class NswETenderingConnector(BaseTenderConnector):
    source_id = "nsw_etendering"
    source_name = "NSW eTendering"
    source_url_field = "nsw_etendering_source_url"
    sample_filename = "nsw_etendering.json"

    def normalize(self, record: dict) -> NormalizedTender | None:
        external_id = str(record.get("notice_id") or record.get("id") or "").strip()
        if not external_id:
            return None
        return NormalizedTender(
            source_id=self.source_id,
            source_name=self.source_name,
            external_id=external_id,
            title=record.get("title", "Untitled NSW tender"),
            buyer_name=record.get("agency", "NSW Government"),
            summary=record.get("summary", ""),
            description=record.get("description", record.get("summary", "")),
            procurement_stage=record.get("stage", "open"),
            source_url=record.get("url", "https://www.tenders.nsw.gov.au"),
            published_at=record.get("published_at"),
            closes_at=record.get("closes_at"),
            estimated_value=record.get("estimated_value"),
            state="NSW",
            region=record.get("region", "Sydney"),
            category=record.get("category", "ICT"),
            tags=record.get("tags", []),
            metadata={
                "procurement_method": record.get("procurement_method"),
                "contact": record.get("contact"),
            },
        )
