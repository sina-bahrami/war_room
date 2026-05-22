from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from urllib.parse import unquote, urlparse

import httpx


def _resolve_local_path(location: str) -> Path | None:
    parsed = urlparse(location)
    if parsed.scheme in {"http", "https"}:
        return None
    if parsed.scheme == "file":
        candidate = Path(unquote(parsed.path)).expanduser()
        return candidate if candidate.exists() else None

    candidate = Path(location).expanduser()
    return candidate if candidate.exists() else None


async def load_warroom_snapshot(source: str) -> dict[str, Any]:
    local_path = _resolve_local_path(source)
    if local_path is not None:
        return json.loads(local_path.read_text(encoding="utf-8"))

    async with httpx.AsyncClient(timeout=30) as client:
        response = await client.get(source, follow_redirects=True)
        response.raise_for_status()
    payload = response.json()
    return payload if isinstance(payload, dict) else {}


def normalize_bucket_mapping(mapping: Any) -> dict[str, int]:
    if not isinstance(mapping, dict):
        return {}
    normalized: dict[str, int] = {}
    for key, value in mapping.items():
        try:
            normalized[str(key)] = int(value)
        except (TypeError, ValueError):
            continue
    return normalized
