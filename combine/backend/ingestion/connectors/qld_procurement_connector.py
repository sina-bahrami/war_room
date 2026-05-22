from __future__ import annotations

from common.tender_schema import NormalizedTender
from ingestion.common.base import BaseTenderConnector


class QldProcurementConnector(BaseTenderConnector):
    source_id = "qld_procurement"
    source_name = "Queensland Procurement"
    source_url_field = "qld_procurement_source_url"
    sample_filename = "qld_procurement.json"

    def normalize(self, record: dict) -> NormalizedTender | None:
        external_id = str(record.get("reference") or record.get("id") or "").strip()
        if not external_id:
            return None
        return NormalizedTender(
            source_id=self.source_id,
            source_name=self.source_name,
            external_id=external_id,
            title=record.get("title", "Untitled QLD opportunity"),
            buyer_name=record.get("agency", "Queensland Government"),
            summary=record.get("summary", ""),
            description=record.get("description", record.get("summary", "")),
            procurement_stage=record.get("stage", "open"),
            source_url=record.get("url", "https://www.hpw.qld.gov.au"),
            published_at=record.get("published_at"),
            closes_at=record.get("closes_at"),
            estimated_value=record.get("estimated_value"),
            state="QLD",
            region=record.get("region", "Brisbane"),
            category=record.get("category", "Facilities Management"),
            tags=record.get("tags", []),
            metadata={
                "supplier_briefing": record.get("supplier_briefing"),
                "contact": record.get("contact"),
            },
        )
