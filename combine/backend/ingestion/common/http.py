from __future__ import annotations

import csv
import io
import json
from pathlib import Path
from typing import Any
from urllib.parse import unquote, urlparse

import httpx


async def fetch_records(url: str) -> list[dict[str, Any]]:
    local_path = _resolve_local_path(url)
    if local_path is not None:
        return load_records_from_path(local_path)

    async with httpx.AsyncClient(timeout=30) as client:
        response = await client.get(url, follow_redirects=True)
        response.raise_for_status()
        content_type = response.headers.get("content-type", "").lower()
        if "csv" in content_type or url.lower().endswith(".csv"):
            return list(csv.DictReader(io.StringIO(response.text)))
        return _coerce_json_records(response.json())


def load_sample_records(path: Path) -> list[dict[str, Any]]:
    return load_records_from_path(path)


def load_records_from_path(path: Path) -> list[dict[str, Any]]:
    if path.suffix.lower() == ".csv":
        with path.open("r", encoding="utf-8") as handle:
            return list(csv.DictReader(handle))
    if path.suffix.lower() == ".jsonl":
        records: list[dict[str, Any]] = []
        with path.open("r", encoding="utf-8") as handle:
            for line in handle:
                line = line.strip()
                if not line:
                    continue
                payload = json.loads(line)
                if isinstance(payload, dict):
                    records.append(payload)
        return records
    with path.open("r", encoding="utf-8") as handle:
        return _coerce_json_records(json.load(handle))


def _coerce_json_records(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    if isinstance(payload, dict):
        for key in ("records", "items", "results", "data", "opportunities"):
            value = payload.get(key)
            if isinstance(value, list):
                return [item for item in value if isinstance(item, dict)]
    return []


def _resolve_local_path(location: str) -> Path | None:
    parsed = urlparse(location)
    if parsed.scheme in {"http", "https"}:
        return None
    if parsed.scheme == "file":
        candidate = Path(unquote(parsed.path)).expanduser()
        return candidate if candidate.exists() else None

    candidate = Path(location).expanduser()
    return candidate if candidate.exists() else None
