from __future__ import annotations

from pathlib import Path
from typing import Any

from api.core.config import Settings
from common.tender_schema import NormalizedTender
from ingestion.common.http import fetch_records, load_sample_records


class BaseTenderConnector:
    source_id: str = ""
    source_name: str = ""
    source_url_field: str = ""
    sample_filename: str = ""
    is_internal: bool = False

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    @property
    def source_url(self) -> str:
        return getattr(self.settings, self.source_url_field)

    @property
    def sample_path(self) -> Path:
        return self.settings.sample_dir / self.sample_filename

    async def fetch(self) -> list[NormalizedTender]:
        if self.source_url:
            raw_records = await fetch_records(self.source_url)
        elif self.settings.enable_sample_data:
            raw_records = load_sample_records(self.sample_path)
        else:
            raw_records = []
        return [item for item in (self.normalize(record) for record in raw_records) if item is not None]

    def normalize(self, record: dict[str, Any]) -> NormalizedTender | None:
        raise NotImplementedError
