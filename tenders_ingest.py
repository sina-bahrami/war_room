import argparse
import json
import logging
import sys
import time
import xml.etree.ElementTree as ET
from dataclasses import dataclass, asdict
from datetime import datetime
from typing import Any, Dict, List, Optional

import requests


# -------------------------------------------------
# Logging
# -------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
)
logger = logging.getLogger(__name__)


# -------------------------------------------------
# Constants
# -------------------------------------------------
AUSTENDER_HOME_URL = "https://www.tenders.gov.au/"
AUSTENDER_RSS_URL = "https://www.tenders.gov.au/public_data/rss/rss.xml"
AUSTENDER_REFERER = (
    "https://data.gov.au/data/dataset/latest-approaches-to-markets-listed-on-austender"
)

NSW_HOME_URL = "https://www.tenders.nsw.gov.au/"
NSW_BASE_URL = "https://www.tenders.nsw.gov.au/"

DEFAULT_TIMEOUT = 45
NSW_MIN_REQUEST_INTERVAL_SECONDS = 1.0


# -------------------------------------------------
# Shared schema
# -------------------------------------------------
@dataclass
class TenderRecord:
    source: str
    source_type: str
    external_id: str
    title: Optional[str]
    summary: Optional[str]
    issuer: Optional[str]
    status: Optional[str]
    publish_date: Optional[str]
    close_date: Optional[str]
    category: Optional[str]
    region: Optional[str]
    value: Optional[Any]
    currency: Optional[str]
    url: Optional[str]
    raw: Dict[str, Any]


# -------------------------------------------------
# Helpers
# -------------------------------------------------
def clean_text(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    value = " ".join(str(value).split())
    return value or None


def parse_possible_date(value: Optional[str]) -> Optional[str]:
    if not value:
        return None

    value = value.strip()
    fmts = [
        "%a, %d %b %Y %H:%M:%S %Z",  # RSS
        "%d-%b-%Y",                  # NSW search params style
        "%Y-%m-%d",
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%d %H:%M:%S",
    ]
    for fmt in fmts:
        try:
            return datetime.strptime(value, fmt).isoformat()
        except ValueError:
            pass
    return value


def first_nonempty(*values):
    for v in values:
        if v not in (None, "", [], {}):
            return v
    return None


def write_jsonl(records: List[TenderRecord], path: str) -> None:
    with open(path, "w", encoding="utf-8") as f:
        for r in records:
            f.write(json.dumps(asdict(r), ensure_ascii=False) + "\n")
    logger.info("Wrote %d records to %s", len(records), path)


# -------------------------------------------------
# Base connector
# -------------------------------------------------
class BaseConnector:
    def __init__(self, timeout: int = DEFAULT_TIMEOUT):
        self.timeout = timeout
        self.session = requests.Session()

        # Browser-like default headers
        self.session.headers.update(
            {
                "User-Agent": (
                    "Mozilla/5.0 (X11; Linux x86_64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/124.0.0.0 Safari/537.36"
                ),
                "Accept-Language": "en-AU,en;q=0.9",
                "Cache-Control": "no-cache",
                "Pragma": "no-cache",
                "DNT": "1",
                "Connection": "keep-alive",
            }
        )

    def get(self, url: str, **kwargs) -> requests.Response:
        resp = self.session.get(url, timeout=self.timeout, **kwargs)
        if resp.status_code == 403:
            logger.error("403 for URL: %s", resp.url)
            logger.error("Response headers: %s", dict(resp.headers))
        resp.raise_for_status()
        return resp


# -------------------------------------------------
# AusTender connector
# -------------------------------------------------
class AusTenderConnector(BaseConnector):
    def warm_session(self) -> None:
        """
        Warm cookies/session on the home page before hitting the RSS URL.
        """
        logger.info("Warming AusTender session via %s", AUSTENDER_HOME_URL)
        self.get(
            AUSTENDER_HOME_URL,
            headers={
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Referer": AUSTENDER_REFERER,
            },
        )

    def fetch_current_atms(self) -> List[TenderRecord]:
        self.warm_session()

        logger.info("Fetching AusTender RSS feed: %s", AUSTENDER_RSS_URL)
        resp = self.get(
            AUSTENDER_RSS_URL,
            headers={
                "Accept": "application/rss+xml, application/xml, text/xml;q=0.9, */*;q=0.8",
                "Referer": AUSTENDER_REFERER,
            },
            allow_redirects=True,
        )

        root = ET.fromstring(resp.text)
        items = root.findall(".//item")

        records: List[TenderRecord] = []

        for item in items:
            title = clean_text(item.findtext("title"))
            link = clean_text(item.findtext("link"))
            description = clean_text(item.findtext("description"))
            pub_date = parse_possible_date(item.findtext("pubDate"))
            guid = clean_text(item.findtext("guid"))

            external_id = first_nonempty(guid, link, title)

            raw = {}
            for child in item:
                raw[child.tag] = clean_text(child.text)

            records.append(
                TenderRecord(
                    source="austender",
                    source_type="approach_to_market",
                    external_id=str(external_id),
                    title=title,
                    summary=description,
                    issuer=None,
                    status="open",
                    publish_date=pub_date,
                    close_date=None,
                    category=None,
                    region="Australia",
                    value=None,
                    currency="AUD",
                    url=link,
                    raw=raw,
                )
            )

        logger.info("Fetched %d AusTender records", len(records))
        return records


# -------------------------------------------------
# NSW eTendering connector
# -------------------------------------------------
class NSWETenderingConnector(BaseConnector):
    def __init__(
        self,
        timeout: int = DEFAULT_TIMEOUT,
        min_interval_seconds: float = NSW_MIN_REQUEST_INTERVAL_SECONDS,
    ):
        super().__init__(timeout=timeout)
        self.min_interval_seconds = min_interval_seconds
        self._last_request_ts = 0.0

    def _throttle(self) -> None:
        elapsed = time.time() - self._last_request_ts
        if elapsed < self.min_interval_seconds:
            time.sleep(self.min_interval_seconds - elapsed)

    def warm_session(self) -> None:
        logger.info("Warming NSW session via %s", NSW_HOME_URL)
        self.get(
            NSW_HOME_URL,
            headers={
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Referer": NSW_HOME_URL,
            },
        )

    def _request_json(self, params: Dict[str, Any]) -> Any:
        self._throttle()

        resp = self.get(
            NSW_BASE_URL,
            params=params,
            headers={
                "Accept": "application/json, text/javascript, */*;q=0.8",
                "Referer": NSW_HOME_URL,
                "X-Requested-With": "XMLHttpRequest",
            },
            allow_redirects=True,
        )
        self._last_request_ts = time.time()

        # Guard against being redirected to a non-API landing page
        final_url = resp.url.lower()
        if "buy.nsw.gov.au" in final_url:
            raise RuntimeError(
                f"Redirected away from NSW eTendering API to {resp.url}. "
                "This usually means the site rejected the request shape."
            )

        content_type = resp.headers.get("Content-Type", "").lower()
        if "json" not in content_type:
            # Sometimes an HTML page is returned instead of JSON.
            snippet = resp.text[:300].replace("\n", " ")
            raise RuntimeError(
                f"Expected JSON but got Content-Type={content_type}. "
                f"Final URL={resp.url}. Response starts with: {snippet}"
            )

        return resp.json()

    def search_tenders(
        self,
        modified_from: Optional[str] = None,
        keyword: Optional[str] = None,
        rft_type: str = "published",
        startrow: int = 0,
    ) -> Any:
        params: Dict[str, Any] = {
            "event": "public.api.tender.search",
            "rftType": rft_type,
            "startrow": startrow,
        }
        if modified_from:
            params["modifiedFrom"] = modified_from
        if keyword:
            params["keyword"] = keyword

        logger.info("Searching NSW tenders with params=%s", params)
        return self._request_json(params)

    def view_tender(self, rft_uuid: str) -> Any:
        params = {
            "event": "public.api.tender.view",
            "RFTUUID": rft_uuid,
        }
        logger.info("Fetching NSW tender detail for RFTUUID=%s", rft_uuid)
        return self._request_json(params)

    @staticmethod
    def _extract_list(payload: Any) -> List[Dict[str, Any]]:
        if isinstance(payload, list):
            return [x for x in payload if isinstance(x, dict)]

        if isinstance(payload, dict):
            for key in ("results", "items", "data", "tenders", "searchResults", "result"):
                if isinstance(payload.get(key), list):
                    return [x for x in payload[key] if isinstance(x, dict)]

            return [payload]

        return []

    @staticmethod
    def _extract_uuid(record: Dict[str, Any]) -> Optional[str]:
        for key in ("RFTUUID", "rftUUID", "uuid", "UUID", "id"):
            if record.get(key):
                return str(record[key])
        return None

    def _normalize_summary_only(self, summary: Dict[str, Any]) -> TenderRecord:
        return TenderRecord(
            source="nsw_etendering",
            source_type="tender",
            external_id=str(
                first_nonempty(
                    self._extract_uuid(summary),
                    summary.get("RFTID"),
                    summary.get("id"),
                    summary.get("Title"),
                )
            ),
            title=clean_text(first_nonempty(summary.get("title"), summary.get("Title"), summary.get("Name"))),
            summary=clean_text(first_nonempty(summary.get("description"), summary.get("Description"))),
            issuer=clean_text(first_nonempty(summary.get("agency"), summary.get("Agency"), summary.get("agencyName"))),
            status=clean_text(first_nonempty(summary.get("status"), summary.get("Status"), summary.get("rftType"))),
            publish_date=parse_possible_date(first_nonempty(summary.get("publishDate"), summary.get("PublishDate"))),
            close_date=parse_possible_date(first_nonempty(summary.get("closeDate"), summary.get("CloseDate"))),
            category=clean_text(first_nonempty(summary.get("category"), summary.get("Category"))),
            region=clean_text(first_nonempty(summary.get("location"), summary.get("Location"), summary.get("region"))),
            value=first_nonempty(summary.get("value"), summary.get("estimatedValue")),
            currency="AUD",
            url=clean_text(first_nonempty(summary.get("url"), summary.get("URL"), summary.get("link"))),
            raw=summary,
        )

    def _normalize_detail(self, detail: Dict[str, Any], summary: Optional[Dict[str, Any]] = None) -> TenderRecord:
        merged = {}
        if summary:
            merged.update(summary)
        merged.update(detail)

        return TenderRecord(
            source="nsw_etendering",
            source_type="tender",
            external_id=str(
                first_nonempty(
                    self._extract_uuid(merged),
                    merged.get("RFTID"),
                    merged.get("id"),
                    merged.get("Title"),
                )
            ),
            title=clean_text(first_nonempty(merged.get("title"), merged.get("Title"), merged.get("Name"), merged.get("tenderTitle"))),
            summary=clean_text(first_nonempty(merged.get("description"), merged.get("Description"), merged.get("brief"), merged.get("tenderDescription"))),
            issuer=clean_text(first_nonempty(merged.get("agency"), merged.get("Agency"), merged.get("agencyName"), merged.get("buyer"))),
            status=clean_text(first_nonempty(merged.get("status"), merged.get("Status"), merged.get("rftType"))),
            publish_date=parse_possible_date(first_nonempty(merged.get("publishDate"), merged.get("PublishDate"), merged.get("publicationDate"))),
            close_date=parse_possible_date(first_nonempty(merged.get("closeDate"), merged.get("CloseDate"), merged.get("closingDate"))),
            category=clean_text(first_nonempty(merged.get("category"), merged.get("Category"), merged.get("unspsc"), merged.get("UNSPSC"))),
            region=clean_text(first_nonempty(merged.get("location"), merged.get("Location"), merged.get("region"))),
            value=first_nonempty(merged.get("value"), merged.get("estimatedValue"), merged.get("estimatedContractValue")),
            currency=clean_text(merged.get("currency")) or "AUD",
            url=clean_text(first_nonempty(merged.get("url"), merged.get("URL"), merged.get("link"))),
            raw=detail,
        )

    def fetch_changed_tenders(
        self,
        modified_from: Optional[str] = None,
        keyword: Optional[str] = None,
        rft_type: str = "published",
        max_pages: int = 20,
        page_size_guess: int = 20,
    ) -> List[TenderRecord]:
        self.warm_session()

        startrow = 0
        page = 0
        records: List[TenderRecord] = []
        seen = set()

        while page < max_pages:
            payload = self.search_tenders(
                modified_from=modified_from,
                keyword=keyword,
                rft_type=rft_type,
                startrow=startrow,
            )
            rows = self._extract_list(payload)

            if not rows:
                break

            for row in rows:
                rft_uuid = self._extract_uuid(row)

                if not rft_uuid:
                    records.append(self._normalize_summary_only(row))
                    continue

                if rft_uuid in seen:
                    continue
                seen.add(rft_uuid)

                try:
                    detail = self.view_tender(rft_uuid)
                    if isinstance(detail, dict):
                        records.append(self._normalize_detail(detail, row))
                    else:
                        records.append(self._normalize_summary_only(row))
                except Exception as exc:
                    logger.warning(
                        "Failed to hydrate NSW tender %s; keeping summary only. Error=%s",
                        rft_uuid,
                        exc,
                    )
                    records.append(self._normalize_summary_only(row))

            if len(rows) < page_size_guess:
                break

            startrow += len(rows)
            page += 1

        logger.info("Fetched %d NSW records", len(records))
        return records


# -------------------------------------------------
# CLI
# -------------------------------------------------
def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)

    p1 = sub.add_parser("austender")
    p1.add_argument("--output", required=True)

    p2 = sub.add_parser("nsw")
    p2.add_argument("--output", required=True)
    p2.add_argument("--modified-from", help="dd-MMM-yyyy, e.g. 01-Jan-2026")
    p2.add_argument("--keyword")
    p2.add_argument(
        "--rft-type",
        default="published",
        choices=["proposed", "published", "closed", "archived"],
    )

    p3 = sub.add_parser("all")
    p3.add_argument("--austender-output", required=True)
    p3.add_argument("--nsw-output", required=True)
    p3.add_argument("--modified-from", help="dd-MMM-yyyy, e.g. 01-Jan-2026")
    p3.add_argument("--keyword")
    p3.add_argument(
        "--rft-type",
        default="published",
        choices=["proposed", "published", "closed", "archived"],
    )

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    try:
        if args.command == "austender":
            records = AusTenderConnector().fetch_current_atms()
            write_jsonl(records, args.output)
            return 0

        if args.command == "nsw":
            records = NSWETenderingConnector().fetch_changed_tenders(
                modified_from=args.modified_from,
                keyword=args.keyword,
                rft_type=args.rft_type,
            )
            write_jsonl(records, args.output)
            return 0

        if args.command == "all":
            aust_records = AusTenderConnector().fetch_current_atms()
            nsw_records = NSWETenderingConnector().fetch_changed_tenders(
                modified_from=args.modified_from,
                keyword=args.keyword,
                rft_type=args.rft_type,
            )
            write_jsonl(aust_records, args.austender_output)
            write_jsonl(nsw_records, args.nsw_output)
            return 0

        return 2

    except requests.HTTPError as exc:
        logger.error("HTTP error: %s", exc)
        return 1
    except Exception as exc:
        logger.exception("Fatal error: %s", exc)
        return 1


if __name__ == "__main__":
    sys.exit(main())
