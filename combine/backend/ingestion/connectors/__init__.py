from __future__ import annotations

from api.core.config import Settings
from ingestion.connectors.austender_connector import AusTenderConnector
from ingestion.connectors.nsw_etendering_connector import NswETenderingConnector
from ingestion.connectors.prompcorp_pipeline_importer import PrompcorpPipelineImporter
from ingestion.connectors.qld_procurement_connector import QldProcurementConnector
from ingestion.connectors.vic_tenders_connector import VicTendersConnector
from ingestion.connectors.warroom_unified_json import WarroomUnifiedJsonConnector


def build_connectors(settings: Settings):
    if settings.warroom_json_source_url:
        return [WarroomUnifiedJsonConnector(settings)]
    return [
        AusTenderConnector(settings),
        NswETenderingConnector(settings),
        VicTendersConnector(settings),
        QldProcurementConnector(settings),
        PrompcorpPipelineImporter(settings),
    ]
