from __future__ import annotations

import json
import math
import re
from pathlib import Path
from typing import Any
from urllib.parse import unquote, urlparse

from common.tender_schema import NormalizedTender
from ingestion.common.base import BaseTenderConnector


class VicTendersConnector(BaseTenderConnector):
    source_id = "vic_tenders"
    source_name = "VIC Tenders and Contracts"
    source_url_field = "vic_tenders_source_url"
    sample_filename = "vic_tenders.json"

    async def fetch(self) -> list[NormalizedTender]:
        export_dir = self._resolve_export_dir()
        if export_dir is not None:
            return self._load_ckan_export(export_dir)
        return await super().fetch()

    def normalize(self, record: dict) -> NormalizedTender | None:
        external_id = str(
            record.get("tender_id")
            or record.get("external_id")
            or record.get("id")
            or ""
        ).strip()
        if not external_id:
            return None
        return NormalizedTender(
            source_id=self.source_id,
            source_name=self.source_name,
            external_id=external_id,
            title=record.get("title") or "Untitled VIC opportunity",
            buyer_name=record.get("department") or record.get("buyer_name") or "Victorian Government",
            summary=record.get("summary") or "",
            description=record.get("description") or record.get("summary") or "",
            procurement_stage=record.get("stage") or record.get("procurement_stage") or "open",
            source_url=record.get("url") or record.get("source_url") or "https://www.tenders.vic.gov.au",
            published_at=record.get("published_at"),
            closes_at=record.get("closes_at"),
            estimated_value=record.get("estimated_value"),
            state="VIC",
            region=record.get("region") or "Melbourne",
            category=record.get("category") or "Construction",
            tags=record.get("tags", []),
            metadata={
                "panel": record.get("panel"),
                "procurement_unit": record.get("procurement_unit"),
            },
        )

    def _resolve_export_dir(self) -> Path | None:
        if not self.source_url:
            return None
        parsed = urlparse(self.source_url)
        if parsed.scheme in {"http", "https"}:
            return None

        if parsed.scheme == "file":
            candidate = Path(unquote(parsed.path)).expanduser()
        else:
            candidate = Path(self.source_url).expanduser()
        if candidate.exists() and candidate.is_dir():
            return candidate
        return None

    def _load_ckan_export(self, root: Path) -> list[NormalizedTender]:
        tenders: list[NormalizedTender] = []
        for dataset_dir in sorted(path for path in root.iterdir() if path.is_dir()):
            metadata_path = dataset_dir / "metadata.json"
            manifest_path = dataset_dir / "manifest.json"
            if not metadata_path.exists():
                continue

            metadata = self._load_json(metadata_path)
            manifest = self._load_json(manifest_path) if manifest_path.exists() else []
            if not isinstance(metadata, dict) or not isinstance(manifest, list):
                continue

            for manifest_entry in manifest:
                if not isinstance(manifest_entry, dict):
                    continue
                output_name = manifest_entry.get("output_file")
                if not output_name:
                    continue
                payload_path = dataset_dir / str(output_name)
                if not payload_path.exists():
                    continue
                payload = self._load_json(payload_path)
                tenders.extend(self._payload_to_tenders(metadata, manifest_entry, payload))
        return tenders

    def _payload_to_tenders(
        self,
        metadata: dict[str, Any],
        manifest_entry: dict[str, Any],
        payload: Any,
    ) -> list[NormalizedTender]:
        if not isinstance(payload, dict):
            return []

        dataset_id = str(metadata.get("id") or metadata.get("name") or "vic-ckan")
        resource_id = str(payload.get("resource_id") or manifest_entry.get("resource_id") or "resource")
        resource_name = str(payload.get("resource_name") or manifest_entry.get("resource_name") or resource_id)
        source_url = str(payload.get("source_url") or self._resource_url(metadata, resource_id) or "https://discover.data.vic.gov.au")

        tenders: list[NormalizedTender] = []
        if isinstance(payload.get("records"), list):
            tenders.extend(
                self._records_to_tenders(
                    metadata=metadata,
                    resource_id=resource_id,
                    resource_name=resource_name,
                    source_url=source_url,
                    records=payload["records"],
                )
            )
        elif isinstance(payload.get("sheets"), dict):
            for sheet_name, rows in payload["sheets"].items():
                if str(sheet_name).strip().lower() == "contents":
                    continue
                if isinstance(rows, list):
                    if not self._should_process_sheet(str(sheet_name), rows, metadata):
                        continue
                    tenders.extend(
                        self._records_to_tenders(
                            metadata=metadata,
                            resource_id=resource_id,
                            resource_name=resource_name,
                            source_url=source_url,
                            records=rows,
                            sheet_name=str(sheet_name),
                        )
                    )
        elif isinstance(payload.get("data"), list):
            tenders.extend(
                self._records_to_tenders(
                    metadata=metadata,
                    resource_id=resource_id,
                    resource_name=resource_name,
                    source_url=source_url,
                    records=payload["data"],
                )
            )
        return tenders

    def _records_to_tenders(
        self,
        *,
        metadata: dict[str, Any],
        resource_id: str,
        resource_name: str,
        source_url: str,
        records: list[Any],
        sheet_name: str | None = None,
    ) -> list[NormalizedTender]:
        tenders: list[NormalizedTender] = []
        dataset_id = str(metadata.get("id") or metadata.get("name") or "vic-ckan")
        dataset_title = str(metadata.get("title") or metadata.get("name") or dataset_id)
        buyer_name = str(metadata.get("organization") or "Victorian Government")
        category = self._infer_category(dataset_title, metadata.get("tags"))
        tags = [str(tag).strip() for tag in metadata.get("tags", []) if str(tag).strip()]
        if sheet_name:
            tags.append(sheet_name)
        if resource_name:
            tags.append(resource_name)
        tags = list(dict.fromkeys(tags))

        for index, raw_record in enumerate(records, start=1):
            if not isinstance(raw_record, dict):
                continue
            record = self._clean_record(raw_record)
            if self._should_skip_record(record):
                continue

            title = self._extract_title(record) or f"{dataset_title} row {index}"
            summary = self._build_summary(dataset_title, resource_name, record, title, sheet_name)
            description = self._build_description(record)
            published_at = self._extract_date(record, ("publish", "issue", "received", "created", "date"))
            closes_at = self._extract_date(record, ("close", "closing", "deadline", "due", "expiry"))
            estimated_value = self._extract_amount(record)
            region = self._extract_region(record)
            external_id = f"{dataset_id}:{resource_id}:{sheet_name or 'records'}:{index}"

            tender = NormalizedTender(
                source_id=self.source_id,
                source_name="VIC Procurement CKAN Export",
                external_id=external_id,
                title=title,
                buyer_name=buyer_name,
                summary=summary,
                description=description,
                procurement_stage="reported",
                source_url=source_url,
                published_at=published_at,
                closes_at=closes_at,
                estimated_value=estimated_value,
                state="VIC",
                region=region,
                category=category,
                tags=tags,
                metadata={
                    "dataset_id": dataset_id,
                    "dataset_title": dataset_title,
                    "resource_id": resource_id,
                    "resource_name": resource_name,
                    "sheet_name": sheet_name,
                    "raw_record": record,
                },
            )
            tenders.append(tender)
        return tenders

    def _resource_url(self, metadata: dict[str, Any], resource_id: str) -> str | None:
        for resource in metadata.get("resources", []):
            if isinstance(resource, dict) and str(resource.get("id")) == resource_id:
                url = resource.get("url")
                if url:
                    return str(url)
        return None

    def _clean_record(self, record: dict[str, Any]) -> dict[str, Any]:
        cleaned: dict[str, Any] = {}
        for key, value in record.items():
            clean_key = str(key).strip()
            if value is None:
                cleaned[clean_key] = None
            elif isinstance(value, float) and math.isnan(value):
                cleaned[clean_key] = None
            elif isinstance(value, str):
                value = value.strip()
                cleaned[clean_key] = value or None
            else:
                cleaned[clean_key] = value
        return cleaned

    def _should_skip_record(self, record: dict[str, Any]) -> bool:
        meaningful_strings = [value for value in record.values() if isinstance(value, str) and value.strip()]
        numeric_values = [value for value in record.values() if isinstance(value, (int, float)) and not isinstance(value, bool)]
        if not meaningful_strings and not numeric_values:
            return True
        if len(meaningful_strings) <= 1 and not numeric_values:
            return True
        joined = " ".join(meaningful_strings).lower()
        if "to receive this data in another format" in joined:
            return True
        if all(str(key).startswith("_") for key in record):
            return True
        return False

    def _extract_title(self, record: dict[str, Any]) -> str | None:
        preferred_fragments = (
            "title",
            "entityname",
            "businessname",
            "supplier",
            "contractor",
            "consultant",
            "project",
            "service",
            "metric",
            "description",
            "objective",
            "outcome",
            "name",
        )
        string_items = [
            (self._normalize_key(key), value)
            for key, value in record.items()
            if isinstance(value, str) and value.strip()
        ]
        for fragment in preferred_fragments:
            for key, value in string_items:
                if fragment in key:
                    return value
        return string_items[0][1] if string_items else None

    def _build_summary(
        self,
        dataset_title: str,
        resource_name: str,
        record: dict[str, Any],
        title: str,
        sheet_name: str | None,
    ) -> str:
        parts = [dataset_title]
        if sheet_name:
            parts.append(sheet_name)
        elif resource_name:
            parts.append(resource_name)

        details: list[str] = []
        for key, value in record.items():
            if value in (None, "", title):
                continue
            if str(key).startswith("_"):
                continue
            details.append(f"{key}: {value}")
            if len(details) == 2:
                break

        if details:
            parts.append(" | ".join(details))
        return " | ".join(parts)

    def _build_description(self, record: dict[str, Any]) -> str:
        details = [
            f"{key}: {value}"
            for key, value in record.items()
            if value not in (None, "") and not str(key).startswith("_")
        ]
        return " | ".join(details[:8])

    def _extract_date(self, record: dict[str, Any], preferred_fragments: tuple[str, ...]) -> Any:
        for key, value in record.items():
            if not value:
                continue
            if not isinstance(value, str):
                continue
            normalized_key = self._normalize_key(key)
            if any(fragment in normalized_key for fragment in preferred_fragments):
                return value
        return None

    def _extract_amount(self, record: dict[str, Any]) -> Any:
        preferred_fragments = ("value", "amount", "expenditure", "spend", "cost", "price", "gst", "aud", "dollar", "total")
        for key, value in record.items():
            normalized_key = self._normalize_key(key)
            if not any(fragment in normalized_key or fragment in str(key).lower() for fragment in preferred_fragments):
                continue
            if isinstance(value, (int, float)) and not isinstance(value, bool):
                return value
            if isinstance(value, str):
                compact = value.replace(",", "").replace("$", "").strip()
                if re.fullmatch(r"-?\d+(\.\d+)?", compact):
                    return value
        return None

    def _extract_region(self, record: dict[str, Any]) -> str:
        for key, value in record.items():
            normalized_key = self._normalize_key(key)
            if isinstance(value, str) and any(fragment in normalized_key for fragment in ("region", "location", "state", "city")):
                return value
        return "Victoria"

    def _infer_category(self, dataset_title: str, tags: Any) -> str:
        joined_tags = " ".join(str(tag) for tag in tags or [])
        text = f"{dataset_title} {joined_tags}".lower()
        if "consult" in text:
            return "Consultancies"
        if "advertising" in text:
            return "Advertising"
        if "ict" in text:
            return "ICT Procurement"
        if "procurement" in text:
            return "Procurement Reporting"
        if "contract" in text:
            return "Contract Reporting"
        return "Victorian Procurement Data"

    def _should_process_sheet(
        self,
        sheet_name: str,
        rows: list[Any],
        metadata: dict[str, Any],
    ) -> bool:
        if self._has_procurement_signal(sheet_name):
            return True

        sample_text_parts = [sheet_name]
        for row in rows[:5]:
            if not isinstance(row, dict):
                continue
            for key, value in row.items():
                if value in (None, ""):
                    continue
                sample_text_parts.append(str(key))
                sample_text_parts.append(str(value))
        sample_text = " ".join(sample_text_parts)
        if self._has_procurement_signal(sample_text):
            return True
        return self._has_money_signal(sample_text)

    def _has_procurement_signal(self, text: str) -> bool:
        lowered = text.lower()
        return any(
            keyword in lowered
            for keyword in (
                "procurement",
                "contract",
                "consult",
                "tender",
                "supplier",
                "advertising",
                "ict",
                "expenditure",
                "spend",
                "fair jobs",
            )
        )

    def _has_money_signal(self, text: str) -> bool:
        lowered = text.lower()
        return any(
            keyword in lowered
            for keyword in ("gst", "$", "amount", "value", "expenditure", "spend", "aud")
        )

    def _normalize_key(self, key: Any) -> str:
        return re.sub(r"[^a-z0-9]+", "", str(key).lower())

    def _load_json(self, path: Path) -> Any:
        return json.loads(path.read_text(encoding="utf-8"))
