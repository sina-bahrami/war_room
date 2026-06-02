from __future__ import annotations

import argparse
import json
import re
from collections import Counter, defaultdict
from copy import deepcopy
from dataclasses import dataclass
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

try:
    from bs4 import BeautifulSoup, Tag
except ImportError as exc:  # pragma: no cover - dependency guard
    raise SystemExit(
        "This script requires beautifulsoup4. Install it with:\n"
        "  python -m pip install beautifulsoup4"
    ) from exc


SCRIPT_DIR = Path(__file__).resolve().parent
DEFAULT_OUTPUT = SCRIPT_DIR / "warroom_dashboard_data.json"
SNAPSHOT_GLOB = "*Prompcorp _ Tenders.Net.html"
SNAPSHOT_DATE_PATTERN = re.compile(r"(?P<day>\d{2})_(?P<month>\d{2})_(?P<year>\d{4})")
TENDER_ID_PATTERN = re.compile(r"^tender(\d+)$")
MONEY_PATTERN = re.compile(
    r"""
    (?P<token>
        \$\s*
        (?P<number>\d[\d,]*(?:\.\d+)?)
        (?:\s*(?P<suffix>k|m|b|thousand|million|billion))?
    )
    """,
    re.IGNORECASE | re.VERBOSE,
)
EMAIL_PATTERN = re.compile(r"([A-Z0-9._%+\-]+@[A-Z0-9.\-]+\.[A-Z]{2,})", re.IGNORECASE)
PHONE_PREFIX_PATTERN = re.compile(
    r"(?:^|\b)(?:P|Ph|Phone|Tel|T)\s*[:\-]?\s*([+()0-9][0-9 +()\-]{7,}[0-9])",
    re.IGNORECASE,
)
PHONE_GENERIC_PATTERN = re.compile(r"([+()0-9][0-9 +()\-]{7,}[0-9])")

AUSTRALIA_STATES = {"ACT", "ALL", "NSW", "NT", "QLD", "SA", "TAS", "VIC", "WA"}
VIEW_BUCKET_ORDER = ["active", "upcoming", "recently_closed", "archived"]
VALUE_BAND_ORDER = ["unknown", "under_100k", "100k_1m", "1m_10m", "10m_plus"]
ALIGNMENT_TO_BRIEF = {
    "supports_views": ["active", "upcoming", "recently_closed"],
    "supports_filters": ["sector_primary", "state", "closing_date", "value_band", "source"],
    "supports_display_fields": ["status", "closing_at", "estimated_value_aud", "agency", "title"],
}
FIELDS_DESCRIPTION = {
    "id": "Stable record id in source:id format.",
    "source": "Normalized source key.",
    "source_record_id": "Native record id from source.",
    "title": "Opportunity title.",
    "description": "Plain-text summary/details for table/detail view and keyword filtering.",
    "agency": "Buyer / issuer / agency name.",
    "state": "ACT/NSW/VIC/QLD/WA/SA/TAS/NT/ALL.",
    "sector_primary": "Primary Prompcorp-facing sector bucket: facility_management, construction, cleaning, other.",
    "sector_tags": "One or more sector tags inferred from title/details.",
    "service_line_relevance": "True if record maps to Prompcorp core sectors.",
    "status": "open or closed.",
    "view_bucket": "Dashboard tab bucket: active, upcoming, recently_closed, archived.",
    "closing_at": "ISO datetime when parseable.",
    "closing_date": "ISO date for date-range filters.",
    "days_to_close": "Days from as_of_date to close date.",
    "closing_soon": "True when 0-7 days remain.",
    "estimated_value_aud": "Parsed monetary amount when a reliable amount-like token exists; null otherwise.",
    "value_band": "Range bucket for filtering and charts.",
    "documents_url": "External documents/info link when present.",
    "contact_email": "First email parsed from contact block when present.",
    "first_seen_at": "First snapshot date observed in provided files.",
    "last_seen_at": "Last snapshot date observed in provided files.",
    "seen_count": "Number of uploaded snapshots containing the record.",
}
SECTOR_RULES: dict[str, tuple[str, ...]] = {
    "cleaning": (
        "cleaning",
        "cleaner",
        "janitorial",
        "washroom",
        "hygiene",
        "laundry",
        "sanitation",
    ),
    "facility_management": (
        "air conditioning",
        "analyst",
        "architect",
        "asset",
        "audit",
        "boiler",
        "canteen",
        "cctv",
        "commissioning",
        "compliance",
        "electrical services",
        "equipment",
        "facility",
        "facilities",
        "fire",
        "fit out",
        "fit-out",
        "furniture",
        "grounds",
        "guardrail",
        "hardware",
        "hydraulic services",
        "inspection",
        "installation",
        "landscaping",
        "lighting",
        "maintenance",
        "mechanical services",
        "mowing",
        "operations",
        "panel",
        "penetration testing",
        "pest",
        "plumbing",
        "refurbishment",
        "repairs",
        "roofing",
        "security",
        "servicing",
        "statement of requirements",
        "storm water",
        "supply",
        "systems",
        "testing",
        "waste",
    ),
    "construction": (
        "amenities block",
        "boardwalk",
        "bridge",
        "brickwork",
        "building",
        "carpark",
        "civil",
        "cladding",
        "concrete",
        "construction",
        "court",
        "deconstruction",
        "demolition",
        "drainage",
        "earthworks",
        "excavation",
        "fencing",
        "footbridge",
        "footpath",
        "framing",
        "greenfield",
        "hall",
        "landfill cell",
        "pathway",
        "pavement",
        "playground",
        "redevelopment",
        "refinery",
        "rehabilitation",
        "reinstatement",
        "retaining wall",
        "road",
        "roof structure",
        "school construction",
        "sewer",
        "shed",
        "site preparation",
        "smelter",
        "sports courts",
        "subdivision",
        "substructure",
        "toilet block",
        "traffic",
        "tunnel",
        "upgrade",
        "wharf",
        "windows",
    ),
}
CLEANING_PRIMARY_TITLE_RULES = ("cleaning", "janitorial", "laundry")


@dataclass(frozen=True)
class ParsedClosing:
    closing_at: str | None
    closing_date: str | None
    closing_date_obj: date | None
    timezone_text: str | None


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build warroom_dashboard_data.json from Prompcorp Tenders.Net HTML snapshots."
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT,
        help="Output JSON path. Defaults to warroom_dashboard_data.json at the repo root.",
    )
    parser.add_argument(
        "--as-of-date",
        type=str,
        default=None,
        help="Override dashboard as_of_date in YYYY-MM-DD format. Defaults to the local current date.",
    )
    return parser.parse_args()


def snapshot_date_from_path(path: Path) -> date:
    match = SNAPSHOT_DATE_PATTERN.search(path.name)
    if match is None:
        raise ValueError(f"Unable to parse snapshot date from filename: {path.name}")
    return date(
        year=int(match.group("year")),
        month=int(match.group("month")),
        day=int(match.group("day")),
    )


def discover_snapshot_files(root: Path) -> list[Path]:
    files = sorted(root.glob(SNAPSHOT_GLOB), key=lambda item: (snapshot_date_from_path(item), item.name))
    if not files:
        raise SystemExit(
            f"No Prompcorp Tenders.Net HTML snapshots found in {root} matching {SNAPSHOT_GLOB!r}."
        )
    return files


def normalize_whitespace(value: str | None) -> str:
    if not value:
        return ""
    return re.sub(r"\s+", " ", value).strip()


def cell_text(cell: Tag | None) -> str:
    if cell is None:
        return ""
    return normalize_whitespace(cell.get_text(" ", strip=True))


def normalize_label(value: str) -> str:
    return normalize_whitespace(value).rstrip(":")


def normalize_state(raw_state: str) -> str:
    state = normalize_whitespace(raw_state).upper()
    state = state.replace("AUSTRALIA WIDE", "ALL").replace("NATIONAL", "ALL")
    return state


def first_href(cell: Tag | None) -> str | None:
    if cell is None:
        return None
    link = cell.find("a", href=True)
    if link is None:
        return None
    href = normalize_whitespace(link.get("href"))
    return href or None


def parse_closing(raw_value: str) -> ParsedClosing:
    raw_value = normalize_whitespace(raw_value)
    if not raw_value or raw_value.lower() == "not stated":
        return ParsedClosing(None, None, None, None)

    pattern = re.compile(
        r"""
        (?P<day>\d{1,2})/(?P<month>\d{1,2})/(?P<year>\d{4})
        (?:\s*-\s*(?P<time>\d{1,2}(?::\d{2})?\s*[ap]\.?\s*m\.?))?
        (?:\s*\((?P<tz>[^)]+)\))?
        """,
        re.IGNORECASE | re.VERBOSE,
    )
    match = pattern.search(raw_value)
    if match is None:
        return ParsedClosing(None, None, None, None)

    closing_day = date(
        year=int(match.group("year")),
        month=int(match.group("month")),
        day=int(match.group("day")),
    )
    closing_at: str | None
    time_text = match.group("time")
    if time_text:
        normalized = normalize_whitespace(time_text).lower().replace(".", "")
        formats = ("%I:%M %p", "%I %p")
        closing_time = None
        for fmt in formats:
            try:
                closing_time = datetime.strptime(normalized.upper(), fmt).time()
                break
            except ValueError:
                continue
        if closing_time is None:
            closing_at = closing_day.isoformat()
        else:
            closing_at = datetime.combine(closing_day, closing_time).isoformat(timespec="seconds")
    else:
        closing_at = closing_day.isoformat()

    timezone_text = normalize_whitespace(match.group("tz")) or None
    return ParsedClosing(closing_at, closing_day.isoformat(), closing_day, timezone_text)


def extract_estimated_value(*chunks: str) -> tuple[float | None, str | None]:
    candidates: list[tuple[float, str]] = []
    for text in chunks:
        if not text:
            continue
        for match in MONEY_PATTERN.finditer(text):
            number_text = match.group("number").replace(",", "")
            try:
                amount = float(number_text)
            except ValueError:
                continue
            suffix = (match.group("suffix") or "").lower()
            if suffix in {"k", "thousand"}:
                amount *= 1_000
            elif suffix in {"m", "million"}:
                amount *= 1_000_000
            elif suffix in {"b", "billion"}:
                amount *= 1_000_000_000
            candidates.append((amount, normalize_whitespace(match.group("token"))))
    if not candidates:
        return None, None
    amount, token = max(candidates, key=lambda item: item[0])
    return amount, token


def extract_email(text: str | None) -> str | None:
    if not text:
        return None
    match = EMAIL_PATTERN.search(text)
    if match is None:
        return None
    return match.group(1)


def extract_phone(text: str | None) -> str | None:
    if not text:
        return None

    preferred = PHONE_PREFIX_PATTERN.search(text)
    if preferred is not None:
        cleaned = normalize_phone(preferred.group(1))
        if cleaned:
            return cleaned

    for match in PHONE_GENERIC_PATTERN.finditer(text):
        cleaned = normalize_phone(match.group(1))
        if cleaned:
            return cleaned
    return None


def normalize_phone(raw_phone: str) -> str | None:
    phone = normalize_whitespace(raw_phone)
    if not phone:
        return None
    digits_only = re.sub(r"\D", "", phone)
    if len(digits_only) < 8:
        return None
    return phone


def infer_sector_tags(title: str, description: str, contact_text: str | None) -> tuple[list[str], str]:
    haystack = " ".join(filter(None, [title, description, contact_text or ""])).lower()
    title_lower = title.lower()
    tags: list[str] = []
    for sector, needles in SECTOR_RULES.items():
        if any(needle in haystack for needle in needles):
            tags.append(sector)

    if not tags:
        return ["other"], "other"
    if "cleaning" in tags and any(needle in title_lower for needle in CLEANING_PRIMARY_TITLE_RULES):
        return tags, "cleaning"
    if "facility_management" in tags:
        return tags, "facility_management"
    if "construction" in tags:
        return tags, "construction"
    if "cleaning" in tags:
        return tags, "other"
    return tags, tags[0]


def choose_value_band(amount: float | None) -> str:
    if amount is None:
        return "unknown"
    if amount < 100_000:
        return "under_100k"
    if amount < 1_000_000:
        return "100k_1m"
    if amount < 10_000_000:
        return "1m_10m"
    return "10m_plus"


def is_invite_only(title: str, description: str, contact_text: str | None) -> bool:
    haystack = " ".join(filter(None, [title, description, contact_text or ""])).lower()
    return "invite only" in haystack or "invited sellers only" in haystack


def is_updated_notice(index_updated: bool, description: str, contact_text: str | None) -> bool:
    haystack = " ".join(filter(None, [description, contact_text or ""])).lower()
    return index_updated or "[updated]" in haystack or "details updated" in haystack or "details added" in haystack


def classify_view_bucket(days_to_close: int | None) -> tuple[str, str]:
    if days_to_close is None:
        return "open", "active"
    if days_to_close < 0:
        if days_to_close >= -29:
            return "closed", "recently_closed"
        return "closed", "archived"
    if days_to_close <= 14:
        return "open", "active"
    return "open", "upcoming"


def latest_non_empty(records: list[dict[str, Any]], key: str, default: Any = None) -> Any:
    for record in reversed(records):
        value = record.get(key)
        if value is None:
            continue
        if isinstance(value, str) and not value.strip():
            continue
        if isinstance(value, list) and not value:
            continue
        if isinstance(value, dict) and not value:
            continue
        return deepcopy(value)
    return deepcopy(default)


def parse_snapshot(path: Path, global_order_start: int) -> tuple[list[dict[str, Any]], int]:
    html = path.read_text(encoding="utf-8", errors="ignore")
    soup = BeautifulSoup(html, "html.parser")
    snapshot_date = snapshot_date_from_path(path).isoformat()

    index_meta: dict[str, dict[str, Any]] = {}
    for anchor in soup.select("#TendersList a[id^=brief]"):
        anchor_id = normalize_whitespace(anchor.get("id"))
        if not anchor_id.startswith("brief"):
            continue
        tender_id = anchor_id.removeprefix("brief")
        title_node = anchor.select_one(".flex-item-topleft")
        title_text = cell_text(title_node)
        updated = "[updated]" in title_text.lower() or anchor.find(class_="sp_updated") is not None
        clean_title = normalize_whitespace(title_text.replace("[Updated]", "").replace("[updated]", ""))
        index_meta[tender_id] = {
            "title": clean_title,
            "is_updated_notice": updated,
        }

    records: list[dict[str, Any]] = []
    global_order = global_order_start

    for container in soup.select("div[id^=tender]"):
        container_id = normalize_whitespace(container.get("id"))
        match = TENDER_ID_PATTERN.match(container_id)
        if match is None:
            continue
        tender_id = match.group(1)
        h2 = container.find("h2")
        title = cell_text(h2) or index_meta.get(tender_id, {}).get("title", "")
        rows: dict[str, Tag] = {}
        for row in container.select("table tr"):
            cells = row.find_all("td")
            if len(cells) < 2:
                continue
            label = normalize_label(cell_text(cells[0]))
            rows[label] = cells[1]

        source_record_id = cell_text(rows.get("Tenders.Net #")) or tender_id
        agency = cell_text(rows.get("Agency"))
        state = normalize_state(cell_text(rows.get("Location")))
        if state not in AUSTRALIA_STATES:
            continue

        closing = parse_closing(cell_text(rows.get("Closing")))
        description = cell_text(rows.get("Details"))
        contact_text = cell_text(rows.get("Contact")) or None
        documents_url = first_href(rows.get("Documentation")) or first_href(rows.get("Lodgement"))
        estimated_value_aud, estimated_value_text = extract_estimated_value(title, description)
        sector_tags, sector_primary = infer_sector_tags(title, description, contact_text)
        index_updated = bool(index_meta.get(tender_id, {}).get("is_updated_notice"))

        records.append(
            {
                "id": f"tenders_net:{source_record_id}",
                "source": "tenders_net",
                "source_record_id": source_record_id,
                "source_url": None,
                "documents_url": documents_url,
                "title": title,
                "description": description,
                "agency": agency,
                "state": state,
                "country": "Australia",
                "market_scope": "australia",
                "sector_primary": sector_primary,
                "sector_tags": sector_tags,
                "service_line_relevance": sector_primary in {"facility_management", "construction", "cleaning"},
                "published_at": None,
                "closing_at": closing.closing_at,
                "closing_date": closing.closing_date,
                "closing_timezone_text": closing.timezone_text,
                "_closing_date_obj": closing.closing_date_obj,
                "estimated_value_aud": estimated_value_aud,
                "estimated_value_text": estimated_value_text,
                "contact_text": contact_text,
                "contact_email": extract_email(contact_text),
                "contact_phone": extract_phone(contact_text),
                "is_invite_only": is_invite_only(title, description, contact_text),
                "is_updated_notice": is_updated_notice(index_updated, description, contact_text),
                "_snapshot_date": snapshot_date,
                "_global_order": global_order,
            }
        )
        global_order += 1

    return records, global_order


def build_opportunities(records: list[dict[str, Any]], as_of_date: date) -> list[dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    first_orders: dict[str, int] = {}
    for record in records:
        record_id = str(record["id"])
        grouped[record_id].append(record)
        first_orders[record_id] = min(first_orders.get(record_id, record["_global_order"]), record["_global_order"])

    opportunities: list[dict[str, Any]] = []
    for record_id in sorted(grouped, key=lambda item: first_orders[item]):
        snapshots = sorted(grouped[record_id], key=lambda item: (item["_snapshot_date"], item["_global_order"]))
        source_file_dates = sorted({item["_snapshot_date"] for item in snapshots})

        closing_date_obj = latest_non_empty(snapshots, "_closing_date_obj")
        days_to_close = None if closing_date_obj is None else (closing_date_obj - as_of_date).days
        status, view_bucket = classify_view_bucket(days_to_close)
        estimated_value_aud = latest_non_empty(snapshots, "estimated_value_aud")
        contact_email = latest_non_empty(snapshots, "contact_email")
        documents_url = latest_non_empty(snapshots, "documents_url")

        opportunity = {
            "id": record_id,
            "source": "tenders_net",
            "source_record_id": latest_non_empty(snapshots, "source_record_id"),
            "source_file_dates": source_file_dates,
            "source_url": None,
            "documents_url": documents_url,
            "title": latest_non_empty(snapshots, "title", ""),
            "description": latest_non_empty(snapshots, "description", ""),
            "agency": latest_non_empty(snapshots, "agency", ""),
            "state": latest_non_empty(snapshots, "state", "ALL"),
            "country": "Australia",
            "market_scope": "australia",
            "sector_primary": latest_non_empty(snapshots, "sector_primary", "other"),
            "sector_tags": latest_non_empty(snapshots, "sector_tags", ["other"]),
            "service_line_relevance": bool(latest_non_empty(snapshots, "service_line_relevance", False)),
            "status": status,
            "view_bucket": view_bucket,
            "published_at": None,
            "closing_at": latest_non_empty(snapshots, "closing_at"),
            "closing_date": latest_non_empty(snapshots, "closing_date"),
            "closing_timezone_text": latest_non_empty(snapshots, "closing_timezone_text"),
            "days_to_close": days_to_close,
            "closing_soon": bool(days_to_close is not None and 0 <= days_to_close <= 7),
            "estimated_value_aud": estimated_value_aud,
            "estimated_value_text": latest_non_empty(snapshots, "estimated_value_text"),
            "value_band": choose_value_band(estimated_value_aud),
            "contact_text": latest_non_empty(snapshots, "contact_text"),
            "contact_email": contact_email,
            "contact_phone": latest_non_empty(snapshots, "contact_phone"),
            "is_invite_only": bool(latest_non_empty(snapshots, "is_invite_only", False)),
            "is_updated_notice": any(bool(item.get("is_updated_notice")) for item in snapshots),
            "first_seen_at": source_file_dates[0],
            "last_seen_at": source_file_dates[-1],
            "seen_count": len(source_file_dates),
            "data_quality": {
                "has_closing_date": latest_non_empty(snapshots, "closing_date") is not None,
                "has_estimated_value": estimated_value_aud is not None,
                "has_documents_url": documents_url is not None,
                "has_contact_email": contact_email is not None,
            },
        }
        opportunities.append(opportunity)

    return opportunities


def counts_dict(items: list[dict[str, Any]], key: str) -> dict[str, int]:
    counter = Counter(str(item.get(key) or "") for item in items if item.get(key) is not None)
    return dict(sorted(counter.items()))


def build_summary(opportunities: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "total_records": len(opportunities),
        "relevant_service_line_records": sum(1 for item in opportunities if item.get("service_line_relevance")),
        "sources": counts_dict(opportunities, "source"),
        "states": counts_dict(opportunities, "state"),
        "sector_primary": counts_dict(opportunities, "sector_primary"),
        "view_buckets": counts_dict(opportunities, "view_bucket"),
        "status": counts_dict(opportunities, "status"),
        "closing_soon_count": sum(1 for item in opportunities if item.get("closing_soon")),
        "estimated_value_available_count": sum(1 for item in opportunities if item.get("estimated_value_aud") is not None),
    }


def build_source_health(opportunities: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if not opportunities:
        return []
    return [
        {
            "source": "tenders_net",
            "record_count": len(opportunities),
            "active_count": sum(1 for item in opportunities if item.get("view_bucket") == "active"),
            "upcoming_count": sum(1 for item in opportunities if item.get("view_bucket") == "upcoming"),
            "recently_closed_count": sum(
                1 for item in opportunities if item.get("view_bucket") == "recently_closed"
            ),
            "estimated_value_available_count": sum(
                1 for item in opportunities if item.get("estimated_value_aud") is not None
            ),
            "first_snapshot_date": min(item["first_seen_at"] for item in opportunities),
            "last_snapshot_date": max(item["last_seen_at"] for item in opportunities),
        }
    ]


def build_filter_options(opportunities: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "states": sorted({item["state"] for item in opportunities}),
        "sector_primary": sorted({item["sector_primary"] for item in opportunities}),
        "sources": sorted({item["source"] for item in opportunities}),
        "view_buckets": VIEW_BUCKET_ORDER,
        "value_bands": VALUE_BAND_ORDER,
    }


def generate_payload(opportunities: list[dict[str, Any]], generated_at: datetime, as_of_date: date) -> dict[str, Any]:
    return {
        "schema_version": "warroom_dashboard_seed.v1",
        "generated_at": generated_at.replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "as_of_date": as_of_date.isoformat(),
        "market_scope": "Australia",
        "purpose": "Unified dashboard seed data prepared from Prompcorp Tenders.Net HTML snapshots.",
        "alignment_to_brief": ALIGNMENT_TO_BRIEF,
        "summary": build_summary(opportunities),
        "source_health": build_source_health(opportunities),
        "filter_options": build_filter_options(opportunities),
        "fields": FIELDS_DESCRIPTION,
        "opportunities": opportunities,
    }


def main() -> None:
    args = parse_args()
    as_of_date = (
        date.fromisoformat(args.as_of_date)
        if args.as_of_date
        else datetime.now().astimezone().date()
    )

    snapshot_files = discover_snapshot_files(SCRIPT_DIR)
    records: list[dict[str, Any]] = []
    global_order = 0
    for path in snapshot_files:
        parsed, global_order = parse_snapshot(path, global_order)
        records.extend(parsed)

    opportunities = build_opportunities(records, as_of_date=as_of_date)
    payload = generate_payload(
        opportunities=opportunities,
        generated_at=datetime.now(timezone.utc),
        as_of_date=as_of_date,
    )

    output_path = args.output if args.output.is_absolute() else SCRIPT_DIR / args.output
    output_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print(f"Wrote {len(opportunities)} opportunities to {output_path}")
    print(f"Snapshots processed: {len(snapshot_files)}")
    print(f"as_of_date: {as_of_date.isoformat()}")


if __name__ == "__main__":
    main()
