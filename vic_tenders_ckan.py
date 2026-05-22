import argparse
import io
import json
import logging
import re
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

import pandas as pd
import requests


# -------------------------------------------------
# Config
# -------------------------------------------------
CKAN_ACTION_BASE = "https://discover.data.vic.gov.au/api/3/action"
DEFAULT_TIMEOUT = 45
DEFAULT_LIMIT = 100
USER_AGENT = "vic-tenders-ckan-ingestor/1.0"
DEFAULT_MIN_RELEVANCE_SCORE = 2
TABULAR_FORMATS = {"csv", "xls", "xlsx", "json"}
PROCUREMENT_KEYWORDS = {
    "procurement",
    "contract",
    "contracts",
    "tender",
    "tenders",
    "supplier",
    "purchasing",
    "expenditure",
    "spend",
    "consulting",
    "consultancy",
    "consultancies",
    "ict",
    "advertising",
}
ORG_SIGNAL_KEYWORDS = {
    "department",
    "agency",
    "authority",
    "board",
    "commission",
    "government",
    "victoria",
    "victorian",
    "office",
    "service",
}
NON_DATA_FORMATS = {
    "html",
    "htm",
    "pdf",
    "png",
    "jpg",
    "jpeg",
    "gif",
    "svg",
    "doc",
    "docx",
    "ppt",
    "pptx",
}
NON_DATA_HINTS = {
    "landing page",
    "documentation",
    "document",
    "fact sheet",
    "guide",
    "brochure",
    "image",
    "preview",
    "web page",
    "webpage",
}
STRUCTURED_CONTENT_TYPE_MAP = {
    "application/json": "json",
    "application/ld+json": "json",
    "text/json": "json",
    "text/csv": "csv",
    "application/csv": "csv",
    "application/vnd.ms-excel": "xls",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": "xlsx",
}
STRUCTURED_HINT_EXTENSIONS = {".csv", ".json", ".xls", ".xlsx"}
NON_DATA_EXTENSIONS = {
    ".html",
    ".htm",
    ".pdf",
    ".png",
    ".jpg",
    ".jpeg",
    ".gif",
    ".svg",
    ".doc",
    ".docx",
    ".ppt",
    ".pptx",
}

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
)
logger = logging.getLogger(__name__)


@dataclass
class DatasetFetchResult:
    dataset_id: str
    dataset_title: str
    selected_resources: int = 0
    saved_resources: int = 0
    failed_resources: int = 0
    unavailable_resources: int = 0
    skipped_reason: Optional[str] = None
    skip_report: Optional[Dict[str, Any]] = None


@dataclass
class SearchSummary:
    datasets_returned: int = 0
    datasets_considered_relevant: int = 0
    datasets_successfully_saved: int = 0
    datasets_skipped_by_relevance: int = 0
    datasets_skipped_no_usable_resources: int = 0
    resource_files_saved: int = 0
    resource_failures: int = 0


class ResourceUnavailableError(RuntimeError):
    pass


# -------------------------------------------------
# Helpers
# -------------------------------------------------
def slugify(value: str) -> str:
    value = value.strip().lower()
    value = re.sub(r"[^a-z0-9]+", "-", value)
    return value.strip("-") or "dataset"


def ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def write_json(path: Path, payload: Any) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)


def normalize_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, list):
        value = " ".join(str(item) for item in value)
    return " ".join(str(value).strip().lower().split())


def is_tabular_format(fmt: Optional[str]) -> bool:
    if not fmt:
        return False
    return fmt.strip().lower() in TABULAR_FORMATS


def keyword_hits(text: str) -> set[str]:
    normalized = normalize_text(text)
    hits: set[str] = set()
    for keyword in PROCUREMENT_KEYWORDS:
        pattern = r"(?<![a-z0-9])" + re.escape(keyword) + r"(?![a-z0-9])"
        if re.search(pattern, normalized):
            hits.add(keyword)
    return hits


def title_name_text(package: Dict[str, Any]) -> str:
    return " ".join(
        filter(
            None,
            [
                str(package.get("title") or ""),
                str(package.get("name") or ""),
            ],
        )
    )


def tag_text(package: Dict[str, Any]) -> str:
    return " ".join(
        str(tag.get("name") or "")
        for tag in package.get("tags", [])
        if isinstance(tag, dict)
    )


def resource_name_text(package: Dict[str, Any]) -> str:
    return " ".join(
        str(resource.get("name") or "")
        for resource in package_resources(package)
    )


def package_title(package: Dict[str, Any]) -> str:
    return str(package.get("title") or package.get("name") or package.get("id") or "unknown dataset")


def package_identifier(package: Dict[str, Any]) -> str:
    return str(package.get("id") or package.get("name") or package_title(package))


def package_resources(package: Dict[str, Any]) -> List[Dict[str, Any]]:
    resources = package.get("resources", [])
    return [resource for resource in resources if isinstance(resource, dict)]


def resource_summary(resource: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "id": resource.get("id"),
        "name": resource.get("name"),
        "format": resource.get("format"),
        "url": resource.get("url"),
        "datastore_active": resource.get("datastore_active"),
    }


def organization_title(package: Dict[str, Any]) -> str:
    organization = package.get("organization") or {}
    if isinstance(organization, dict):
        return str(organization.get("title") or organization.get("name") or "")
    return str(organization or "")


def resource_path_extension(value: Optional[str]) -> str:
    if not value:
        return ""
    path = urlparse(str(value)).path
    return Path(path).suffix.lower()


def infer_structured_format(
    resource: Dict[str, Any],
    content_type: Optional[str] = None,
) -> Optional[str]:
    fmt = normalize_text(resource.get("format"))
    if fmt in TABULAR_FORMATS:
        return fmt

    candidates = [
        resource.get("url"),
        resource.get("name"),
    ]
    for candidate in candidates:
        ext = resource_path_extension(candidate)
        if ext in STRUCTURED_HINT_EXTENSIONS:
            return ext.lstrip(".")

    normalized_content_type = normalize_text(content_type)
    for content_type_prefix, mapped_format in STRUCTURED_CONTENT_TYPE_MAP.items():
        if normalized_content_type.startswith(content_type_prefix):
            return mapped_format

    return None


def is_clearly_non_data_resource(resource: Dict[str, Any]) -> bool:
    fmt = normalize_text(resource.get("format"))
    if fmt in NON_DATA_FORMATS:
        return True

    for candidate in (resource.get("url"), resource.get("name")):
        ext = resource_path_extension(candidate)
        if ext in NON_DATA_EXTENSIONS:
            return True

    combined_text = " ".join(
        filter(
            None,
            [
                normalize_text(resource.get("name")),
                normalize_text(resource.get("url")),
                normalize_text(resource.get("description")),
            ],
        )
    )
    return any(hint in combined_text for hint in NON_DATA_HINTS)


def is_probably_structured_resource(resource: Dict[str, Any]) -> bool:
    if resource.get("datastore_active"):
        return True
    if infer_structured_format(resource):
        return True

    combined_text = " ".join(
        filter(
            None,
            [
                normalize_text(resource.get("name")),
                normalize_text(resource.get("url")),
            ],
        )
    )
    return any(token in combined_text for token in ("download", "api", "export")) and not is_clearly_non_data_resource(resource)


def build_skip_report_entry(package: Dict[str, Any], reason: str) -> Dict[str, Any]:
    return {
        "dataset_id": package_identifier(package),
        "dataset_title": package_title(package),
        "reason": reason,
        "resources": [resource_summary(resource) for resource in package_resources(package)],
    }


def has_primary_procurement_signal(package: Dict[str, Any]) -> bool:
    return any(
        keyword_hits(text)
        for text in (
            title_name_text(package),
            tag_text(package),
            resource_name_text(package),
        )
    )


def score_dataset_relevance(package: Dict[str, Any]) -> tuple[int, List[str]]:
    reasons: List[str] = []
    score = 0

    title_name_hits = keyword_hits(title_name_text(package))
    if title_name_hits:
        score += 2
        reasons.append("title/name")

    notes_hits = keyword_hits(str(package.get("notes") or ""))
    if notes_hits:
        score += 1
        reasons.append("notes")

    tag_hits = keyword_hits(tag_text(package))
    if tag_hits:
        score += 1
        reasons.append("tags")

    resource_hits = keyword_hits(resource_name_text(package))
    if resource_hits:
        score += 1
        reasons.append("resource names")

    has_any_procurement_signal = bool(title_name_hits or notes_hits or tag_hits or resource_hits)
    org_text = organization_title(package)
    org_signals = has_any_procurement_signal and any(
        keyword in normalize_text(org_text) for keyword in ORG_SIGNAL_KEYWORDS
    )
    if org_signals:
        score += 1
        reasons.append("organization")

    return score, reasons


def relevance_skip_reason(
    package: Dict[str, Any],
    score: int,
    min_score: int,
    has_primary_signal: bool,
) -> str:
    keyword_signal_text = " ".join(
        filter(
            None,
            [
                str(package.get("title") or ""),
                str(package.get("name") or ""),
                str(package.get("notes") or ""),
                organization_title(package),
                " ".join(
                    str(tag.get("name") or "")
                    for tag in package.get("tags", [])
                    if isinstance(tag, dict)
                ),
                " ".join(
                    str(resource.get("name") or "")
                    for resource in package_resources(package)
                ),
            ],
        )
    )
    has_procurement_signal = bool(keyword_hits(keyword_signal_text))
    if score >= min_score and not has_primary_signal:
        return (
            f"relevance score={score} but no primary procurement signal "
            "(title/name, tags, or resource names)"
        )
    if not has_procurement_signal:
        return (
            f"relevance score={score} below threshold {min_score} and "
            "no procurement-related resources found"
        )
    return f"relevance score={score} below threshold {min_score}"


def log_search_summary(summary: SearchSummary) -> None:
    logger.info("Search summary:")
    logger.info("  datasets returned by search: %d", summary.datasets_returned)
    logger.info("  datasets considered relevant: %d", summary.datasets_considered_relevant)
    logger.info("  datasets successfully saved: %d", summary.datasets_successfully_saved)
    logger.info("  datasets skipped by relevance: %d", summary.datasets_skipped_by_relevance)
    logger.info("  datasets skipped for no usable resources: %d", summary.datasets_skipped_no_usable_resources)
    logger.info("  resource files saved: %d", summary.resource_files_saved)
    logger.info("  resource failures: %d", summary.resource_failures)


# -------------------------------------------------
# CKAN client
# -------------------------------------------------
class DataVicCKANClient:
    def __init__(
        self,
        api_key: Optional[str] = None,
        timeout: int = DEFAULT_TIMEOUT,
        sleep_seconds: float = 2.5,  # conservative: well under 25 req/min
    ) -> None:
        self.timeout = timeout
        self.sleep_seconds = sleep_seconds
        self.session = requests.Session()
        self.session.headers.update(
            {
                "User-Agent": USER_AGENT,
                "Accept": "application/json",
            }
        )
        if api_key:
            # Some environments use Authorization or X-CKAN-API-Key.
            self.session.headers["Authorization"] = api_key
            self.session.headers["X-CKAN-API-Key"] = api_key

    def _sleep(self) -> None:
        time.sleep(self.sleep_seconds)

    def action_get(self, action: str, params: Dict[str, Any]) -> Dict[str, Any]:
        url = f"{CKAN_ACTION_BASE}/{action}"
        logger.info("GET %s params=%s", url, params)
        resp = self.session.get(url, params=params, timeout=self.timeout)
        resp.raise_for_status()
        payload = resp.json()
        if not payload.get("success", False):
            raise RuntimeError(f"CKAN API logic error for {action}: {payload.get('error')}")
        self._sleep()
        return payload["result"]

    def package_search(self, query: str, rows: int = 25, start: int = 0) -> Dict[str, Any]:
        return self.action_get(
            "package_search",
            {
                "q": query,
                "rows": rows,
                "start": start,
            },
        )

    def package_show(self, dataset_id_or_name: str) -> Dict[str, Any]:
        return self.action_get(
            "package_show",
            {"id": dataset_id_or_name},
        )

    def datastore_search(
        self,
        resource_id: str,
        limit: int = 100,
        offset: int = 0,
    ) -> Dict[str, Any]:
        return self.action_get(
            "datastore_search",
            {
                "resource_id": resource_id,
                "limit": limit,
                "offset": offset,
            },
        )

    def download_resource(self, url: str) -> tuple[bytes, str]:
        logger.info("Downloading resource: %s", url)
        head_resp = self.session.head(url, allow_redirects=True, timeout=self.timeout)
        if head_resp.status_code in {404, 410}:
            self._sleep()
            raise ResourceUnavailableError(
                f"{head_resp.status_code} for URL: {head_resp.url}"
            )
        resp = self.session.get(url, timeout=self.timeout)
        resp.raise_for_status()
        self._sleep()
        return resp.content, resp.headers.get("content-type", "")


# -------------------------------------------------
# Resource extraction
# -------------------------------------------------
def extract_datastore_resource(
    client: DataVicCKANClient,
    resource: Dict[str, Any],
    page_size: int = 500,
    max_records: Optional[int] = None,
) -> Dict[str, Any]:
    resource_id = resource["id"]
    offset = 0
    total = None
    records: List[Dict[str, Any]] = []

    while True:
        result = client.datastore_search(
            resource_id=resource_id,
            limit=page_size,
            offset=offset,
        )

        batch = result.get("records", [])
        total = result.get("total", total)
        records.extend(batch)

        logger.info(
            "Fetched datastore batch: resource_id=%s offset=%d batch=%d total_so_far=%d",
            resource_id,
            offset,
            len(batch),
            len(records),
        )

        if not batch:
            break

        offset += len(batch)

        if max_records is not None and len(records) >= max_records:
            records = records[:max_records]
            break

        if total is not None and offset >= total:
            break

    return {
        "resource_id": resource_id,
        "resource_name": resource.get("name"),
        "format": resource.get("format"),
        "source_url": resource.get("url"),
        "records": records,
        "total": total if total is not None else len(records),
    }


def extract_file_resource(
    client: DataVicCKANClient,
    resource: Dict[str, Any],
) -> Dict[str, Any]:
    url = resource.get("url")
    if not url:
        raise ValueError("Resource has no URL")

    raw, content_type = client.download_resource(url)
    fmt = infer_structured_format(resource, content_type=content_type)

    if fmt is None:
        raise ValueError(
            f"Unsupported downloadable resource with unknown format: {resource.get('format')!r}"
        )

    if fmt == "json":
        payload = json.loads(raw.decode("utf-8"))
        return {
            "resource_id": resource.get("id"),
            "resource_name": resource.get("name"),
            "format": fmt,
            "source_url": url,
            "data": payload,
        }

    if fmt == "csv":
        df = pd.read_csv(io.BytesIO(raw))
        return {
            "resource_id": resource.get("id"),
            "resource_name": resource.get("name"),
            "format": fmt,
            "source_url": url,
            "records": df.where(pd.notnull(df), None).to_dict(orient="records"),
        }

    if fmt in {"xls", "xlsx"}:
        sheets = pd.read_excel(io.BytesIO(raw), sheet_name=None)
        payload = {
            sheet_name: sheet_df.where(pd.notnull(sheet_df), None).to_dict(orient="records")
            for sheet_name, sheet_df in sheets.items()
        }
        return {
            "resource_id": resource.get("id"),
            "resource_name": resource.get("name"),
            "format": fmt,
            "source_url": url,
            "sheets": payload,
        }

    raise ValueError(f"Unsupported downloadable format: {fmt}")


# -------------------------------------------------
# Dataset workflow
# -------------------------------------------------
def choose_relevant_resources(package: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Prefer machine-readable resources:
    1) datastore/Data API resources
    2) JSON/CSV/XLSX/XLS resources
    """
    resources = package_resources(package)
    selected: List[Dict[str, Any]] = []
    ambiguous: List[Dict[str, Any]] = []
    selected_ids: set[str] = set()

    def add_selected(resource: Dict[str, Any]) -> None:
        resource_id = str(resource.get("id") or resource.get("url") or resource.get("name"))
        if resource_id in selected_ids:
            return
        selected.append(resource)
        selected_ids.add(resource_id)

    for resource in resources:
        if resource.get("datastore_active"):
            add_selected(resource)

    for resource in resources:
        if resource in selected:
            continue
        if is_probably_structured_resource(resource):
            add_selected(resource)
        elif not is_clearly_non_data_resource(resource):
            ambiguous.append(resource)

    if selected:
        return selected

    return ambiguous


def save_package_metadata(package: Dict[str, Any], out_dir: Path) -> None:
    metadata = {
        "id": package.get("id"),
        "name": package.get("name"),
        "title": package.get("title"),
        "notes": package.get("notes"),
        "organization": (package.get("organization") or {}).get("title"),
        "tags": [t.get("name") for t in package.get("tags", [])],
        "num_resources": len(package.get("resources", [])),
        "resources": [
            {
                "id": r.get("id"),
                "name": r.get("name"),
                "format": r.get("format"),
                "url": r.get("url"),
                "datastore_active": r.get("datastore_active"),
            }
            for r in package.get("resources", [])
        ],
    }
    write_json(out_dir / "metadata.json", metadata)


def fetch_dataset_to_json(
    client: DataVicCKANClient,
    dataset_id_or_name: str,
    output_dir: Path,
    max_records_per_datastore: Optional[int] = None,
) -> DatasetFetchResult:
    package = client.package_show(dataset_id_or_name)
    dataset_name = package_title(package)
    dataset_slug = slugify(package.get("name") or package.get("title") or dataset_id_or_name)
    dataset_dir = output_dir / dataset_slug
    ensure_dir(dataset_dir)
    result = DatasetFetchResult(
        dataset_id=package_identifier(package),
        dataset_title=dataset_name,
    )

    save_package_metadata(package, dataset_dir)

    selected_resources = choose_relevant_resources(package)
    result.selected_resources = len(selected_resources)
    logger.info(
        "Dataset '%s' -> selected %d relevant resources",
        dataset_name,
        len(selected_resources),
    )

    if not selected_resources:
        result.skipped_reason = "No usable machine-readable resources found"
        result.skip_report = build_skip_report_entry(package, result.skipped_reason)
        logger.info(
            "Skipping dataset '%s' because no usable machine-readable resources were found",
            dataset_name,
        )
        return result

    manifest = []

    for resource in selected_resources:
        resource_slug = slugify(resource.get("name") or resource.get("id"))
        out_path = dataset_dir / f"{resource_slug}.json"

        try:
            if resource.get("datastore_active"):
                payload = extract_datastore_resource(
                    client,
                    resource,
                    max_records=max_records_per_datastore,
                )
            else:
                payload = extract_file_resource(client, resource)

            write_json(out_path, payload)
            result.saved_resources += 1

            manifest.append(
                {
                    "resource_id": resource.get("id"),
                    "resource_name": resource.get("name"),
                    "format": resource.get("format"),
                    "datastore_active": resource.get("datastore_active"),
                    "output_file": out_path.name,
                }
            )
            logger.info("Saved %s", out_path)

        except ResourceUnavailableError as exc:
            result.unavailable_resources += 1
            logger.info(
                "Skipping unavailable resource id=%s name=%s: %s",
                resource.get("id"),
                resource.get("name"),
                exc,
            )
        except Exception as exc:
            result.failed_resources += 1
            logger.warning(
                "Failed resource id=%s name=%s: %s",
                resource.get("id"),
                resource.get("name"),
                exc,
            )

    write_json(dataset_dir / "manifest.json", manifest)
    if result.saved_resources == 0 and result.unavailable_resources == result.selected_resources:
        result.skipped_reason = "All candidate resources were unavailable (stale or missing URLs)"
        result.skip_report = build_skip_report_entry(package, result.skipped_reason)
    if result.saved_resources == 0 and result.failed_resources > 0:
        result.skipped_reason = "Selected resources failed to download or parse"
        if result.unavailable_resources > 0:
            result.skipped_reason = "Candidate resources were unavailable or failed to download/parse"
        result.skip_report = build_skip_report_entry(package, result.skipped_reason)
    return result


def search_and_fetch(
    client: DataVicCKANClient,
    query: str,
    output_dir: Path,
    rows: int = 10,
    max_records_per_datastore: Optional[int] = None,
    min_relevance_score: int = DEFAULT_MIN_RELEVANCE_SCORE,
) -> None:
    result = client.package_search(query=query, rows=rows, start=0)
    packages = result.get("results", [])
    summary = SearchSummary(datasets_returned=len(packages))
    logger.info("package_search returned %d datasets", len(packages))

    search_results = []
    relevant_packages: List[Dict[str, Any]] = []
    skipped_datasets: List[Dict[str, Any]] = []
    for pkg in packages:
        relevance_score, relevance_reasons = score_dataset_relevance(pkg)
        primary_signal = has_primary_procurement_signal(pkg)
        is_relevant = relevance_score >= min_relevance_score and primary_signal
        search_results.append(
            {
                "id": pkg.get("id"),
                "name": pkg.get("name"),
                "title": pkg.get("title"),
                "organization": organization_title(pkg),
                "relevance_score": relevance_score,
                "relevance_reasons": relevance_reasons,
                "has_primary_procurement_signal": primary_signal,
                "considered_relevant": is_relevant,
            }
        )
        if is_relevant:
            relevant_packages.append(pkg)
            continue

        summary.datasets_skipped_by_relevance += 1
        reason = relevance_skip_reason(pkg, relevance_score, min_relevance_score, primary_signal)
        logger.info(
            "Skipping dataset '%s' because %s",
            package_title(pkg),
            reason,
        )
        skipped_datasets.append(build_skip_report_entry(pkg, reason))

    summary.datasets_considered_relevant = len(relevant_packages)
    write_json(output_dir / "search_results.json", search_results)

    for pkg in relevant_packages:
        fetch_result = fetch_dataset_to_json(
            client=client,
            dataset_id_or_name=pkg.get("name") or pkg.get("id") or package_identifier(pkg),
            output_dir=output_dir,
            max_records_per_datastore=max_records_per_datastore,
        )
        summary.resource_files_saved += fetch_result.saved_resources
        summary.resource_failures += fetch_result.failed_resources

        if fetch_result.saved_resources > 0:
            summary.datasets_successfully_saved += 1
            continue

        if fetch_result.skipped_reason:
            summary.datasets_skipped_no_usable_resources += 1
            skipped_datasets.append(fetch_result.skip_report or build_skip_report_entry(pkg, fetch_result.skipped_reason))

    write_json(output_dir / "skipped_datasets.json", skipped_datasets)
    log_search_summary(summary)


# -------------------------------------------------
# CLI
# -------------------------------------------------
def build_parser() -> argparse.ArgumentParser:
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument(
        "--api-key",
        default=None,
        help="Optional Developer Victoria / CKAN API key if required for your environment.",
    )
    common.add_argument(
        "--output-dir",
        default="vic_data",
        help="Directory where JSON files will be written.",
    )
    common.add_argument(
        "--sleep-seconds",
        type=float,
        default=2.5,
        help="Delay between requests. Keep this conservative.",
    )

    parser = argparse.ArgumentParser(
        description="Fetch Victorian procurement/tender-related datasets from DataVic CKAN and save as JSON.",
        parents=[common],
    )

    subparsers = parser.add_subparsers(dest="command", required=True)

    p_search = subparsers.add_parser(
        "search",
        help="Search CKAN datasets and fetch matching datasets",
        parents=[common],
    )
    p_search.add_argument(
        "--query",
        default="procurement OR contract OR tender",
        help="CKAN package_search query",
    )
    p_search.add_argument(
        "--rows",
        type=int,
        default=10,
        help="How many matching datasets to process",
    )
    p_search.add_argument(
        "--max-records-per-datastore",
        type=int,
        default=None,
        help="Optional cap for large datastore resources",
    )
    p_search.add_argument(
        "--min-relevance-score",
        type=int,
        default=DEFAULT_MIN_RELEVANCE_SCORE,
        help="Minimum post-search relevance score required before fetching a dataset.",
    )

    p_dataset = subparsers.add_parser(
        "dataset",
        help="Fetch one known dataset by name or id",
        parents=[common],
    )
    p_dataset.add_argument(
        "--id",
        required=True,
        help="Dataset name or id, e.g. dh-annual-report-2023-24-procurement-including-ict-and-advertising",
    )
    p_dataset.add_argument(
        "--max-records-per-datastore",
        type=int,
        default=None,
        help="Optional cap for large datastore resources",
    )

    return parser


def main() -> int:
    args = build_parser().parse_args()
    out_dir = Path(args.output_dir)
    ensure_dir(out_dir)

    client = DataVicCKANClient(
        api_key=args.api_key,
        sleep_seconds=args.sleep_seconds,
    )

    try:
        if args.command == "search":
            search_and_fetch(
                client=client,
                query=args.query,
                output_dir=out_dir,
                rows=args.rows,
                max_records_per_datastore=args.max_records_per_datastore,
                min_relevance_score=args.min_relevance_score,
            )
            return 0

        if args.command == "dataset":
            fetch_dataset_to_json(
                client=client,
                dataset_id_or_name=args.id,
                output_dir=out_dir,
                max_records_per_datastore=args.max_records_per_datastore,
            )
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
