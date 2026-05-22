from __future__ import annotations

from common.tender_schema import NormalizedTender
from ingestion.common.base import BaseTenderConnector


class PrompcorpPipelineImporter(BaseTenderConnector):
    source_id = "prompcorp_pipeline"
    source_name = "Prompcorp Internal Pipeline"
    source_url_field = "prompcorp_pipeline_source_url"
    sample_filename = "prompcorp_pipeline.csv"
    is_internal = True

    def normalize(self, record: dict) -> NormalizedTender | None:
        external_id = str(record.get("opportunity_id") or record.get("id") or "").strip()
        if not external_id:
            return None
        return NormalizedTender(
            source_id=self.source_id,
            source_name=self.source_name,
            external_id=external_id,
            title=record.get("opportunity_name", "Untitled internal opportunity"),
            buyer_name=record.get("client_name", "Prompcorp client"),
            summary=record.get("summary", ""),
            description=record.get("notes", record.get("summary", "")),
            procurement_stage=(record.get("stage") or "qualification").lower(),
            source_url=record.get("url", "https://internal.prompcorp.local/pipeline"),
            published_at=record.get("created_at"),
            closes_at=record.get("target_submission_date"),
            estimated_value=record.get("estimated_value"),
            state=record.get("state", "National"),
            region=record.get("region", ""),
            category=record.get("category", "Consulting"),
            tags=record.get("tags", []),
            status=record.get("status", "active"),
            is_internal=True,
            metadata={
                "bid_lead": record.get("bid_lead"),
                "win_theme": record.get("win_theme"),
                "capture_plan": record.get("capture_plan"),
            },
        )
