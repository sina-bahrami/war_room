from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from dateutil import parser as date_parser
from pydantic import BaseModel, Field, field_validator, model_validator


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def coerce_datetime(value: Any) -> datetime | None:
    if value in (None, "", 0):
        return None
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    if isinstance(value, (int, float)):
        return datetime.fromtimestamp(value, tz=timezone.utc)
    if isinstance(value, str):
        parsed = date_parser.parse(value)
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
    return None


def coerce_amount(value: Any) -> float | None:
    if value in (None, "", "n/a", "N/A"):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        cleaned = (
            value.replace("$", "")
            .replace(",", "")
            .replace("AUD", "")
            .strip()
        )
        try:
            return float(cleaned)
        except ValueError:
            return None
    return None


class NormalizedTender(BaseModel):
    source_id: str
    source_name: str
    external_id: str
    title: str
    buyer_name: str
    summary: str = ""
    description: str = ""
    procurement_stage: str = "open"
    source_url: str
    published_at: datetime | None = None
    closes_at: datetime | None = None
    estimated_value: float | None = None
    currency: str = "AUD"
    state: str = "National"
    region: str = ""
    category: str = "General"
    tags: list[str] = Field(default_factory=list)
    status: str = "active"
    priority_score: float = 0.0
    is_internal: bool = False
    metadata: dict[str, Any] = Field(default_factory=dict)
    last_ingested_at: datetime = Field(default_factory=utc_now)

    @field_validator("published_at", "closes_at", mode="before")
    @classmethod
    def _parse_datetime(cls, value: Any) -> datetime | None:
        return coerce_datetime(value)

    @field_validator("estimated_value", mode="before")
    @classmethod
    def _parse_amount(cls, value: Any) -> float | None:
        return coerce_amount(value)

    @field_validator("tags", mode="before")
    @classmethod
    def _normalize_tags(cls, value: Any) -> list[str]:
        if not value:
            return []
        if isinstance(value, str):
            return [chunk.strip() for chunk in value.split(",") if chunk.strip()]
        if isinstance(value, list):
            return [str(chunk).strip() for chunk in value if str(chunk).strip()]
        return []

    @model_validator(mode="after")
    def _score_priority(self) -> "NormalizedTender":
        urgency = 0.0
        if self.closes_at:
            days_remaining = (self.closes_at - utc_now()).total_seconds() / 86400
            if days_remaining <= 3:
                urgency = 45
            elif days_remaining <= 7:
                urgency = 32
            elif days_remaining <= 14:
                urgency = 18

        value_score = 0.0
        if self.estimated_value:
            if self.estimated_value >= 10_000_000:
                value_score = 35
            elif self.estimated_value >= 2_000_000:
                value_score = 24
            elif self.estimated_value >= 500_000:
                value_score = 12

        stage_bonus = {
            "open": 18,
            "evaluation": 10,
            "qualification": 16,
            "proposal": 20,
            "submitted": 8,
            "award-watch": 6,
        }.get(self.procurement_stage, 8)

        internal_bonus = 10 if self.is_internal else 0
        self.priority_score = round(urgency + value_score + stage_bonus + internal_bonus, 2)
        return self


class SourceRunRecord(BaseModel):
    source_id: str
    source_name: str
    status: str
    records_seen: int
    records_upserted: int
    started_at: datetime
    finished_at: datetime | None = None
    message: str | None = None
