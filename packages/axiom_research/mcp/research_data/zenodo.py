from typing import Any

from axiom_research.mcp.errors import McpRuntimeError
from axiom_research.mcp.research_data.models import ZenodoRecord, ZenodoSearchResult
from axiom_research.mcp.upstream import UpstreamClient

ZENODO_RECORDS = "https://zenodo.org/api/records"


class ZenodoClient:
    """Deposited record metadata (versions, licenses). Not DataCite PID agency."""

    def __init__(self, upstream: UpstreamClient):
        self._upstream = upstream

    async def get_record(self, record_id: str) -> ZenodoRecord:
        cleaned = _normalize_record_id(record_id)
        if not cleaned:
            raise McpRuntimeError("VALIDATION", "record_id must not be empty")
        payload = await self._upstream.get_json(f"{ZENODO_RECORDS}/{cleaned}")
        if not isinstance(payload, dict):
            raise McpRuntimeError("VALIDATION", "Zenodo returned unexpected payload")
        return _normalize_record(payload)

    async def search_records(self, query: str, *, size: int = 5) -> ZenodoSearchResult:
        cleaned = query.strip()
        if not cleaned:
            raise McpRuntimeError("VALIDATION", "query must not be empty")
        if size < 1 or size > 25:
            raise McpRuntimeError("VALIDATION", "size must be between 1 and 25")
        payload = await self._upstream.get_json(
            ZENODO_RECORDS,
            params={"q": cleaned, "size": size, "all_versions": "false"},
        )
        if not isinstance(payload, dict):
            raise McpRuntimeError("VALIDATION", "Zenodo returned unexpected payload")
        hits_block = payload.get("hits") if isinstance(payload.get("hits"), dict) else {}
        hits = hits_block.get("hits") if isinstance(hits_block.get("hits"), list) else []
        records = [_normalize_record(item) for item in hits if isinstance(item, dict)]
        total = hits_block.get("total")
        if isinstance(total, dict):
            count = int(total.get("value") or len(records))
        elif isinstance(total, int):
            count = total
        else:
            count = len(records)
        return ZenodoSearchResult(query=cleaned, count=count, records=records)


def _normalize_record_id(record_id: str) -> str:
    cleaned = record_id.strip()
    for prefix in (
        "https://zenodo.org/records/",
        "http://zenodo.org/records/",
        "https://zenodo.org/record/",
        "doi:10.5281/zenodo.",
        "10.5281/zenodo.",
    ):
        if cleaned.lower().startswith(prefix.lower()):
            cleaned = cleaned[len(prefix) :]
            break
    return cleaned.strip().rstrip("/")


def _normalize_record(raw: dict[str, Any]) -> ZenodoRecord:
    metadata = raw.get("metadata") if isinstance(raw.get("metadata"), dict) else {}
    license_obj = metadata.get("license") if isinstance(metadata.get("license"), dict) else {}
    resource = (
        metadata.get("resource_type") if isinstance(metadata.get("resource_type"), dict) else {}
    )
    files = raw.get("files") if isinstance(raw.get("files"), list) else []
    record_id = str(raw.get("id") or raw.get("recid") or "")
    if not record_id:
        raise McpRuntimeError("VALIDATION", "Zenodo record missing id")
    return ZenodoRecord(
        record_id=record_id,
        concept_recid=str(raw["conceptrecid"]) if raw.get("conceptrecid") else None,
        doi=str(raw["doi"]) if raw.get("doi") else None,
        conceptdoi=str(raw["conceptdoi"]) if raw.get("conceptdoi") else None,
        title=str(metadata["title"]) if metadata.get("title") else None,
        publication_date=str(metadata["publication_date"])
        if metadata.get("publication_date")
        else None,
        version=str(metadata["version"]) if metadata.get("version") else None,
        resource_type=str(resource.get("type") or resource.get("title") or "") or None,
        access_right=str(metadata["access_right"]) if metadata.get("access_right") else None,
        license_id=str(license_obj["id"]) if license_obj.get("id") else None,
        license_url=_license_url(license_obj),
        files_count=len(files),
        record_url=str(raw["links"]["html"])
        if isinstance(raw.get("links"), dict) and raw["links"].get("html")
        else f"https://zenodo.org/records/{record_id}",
    )


def _license_url(license_obj: dict[str, Any]) -> str | None:
    if license_obj.get("url"):
        return str(license_obj["url"])
    links = license_obj.get("links") if isinstance(license_obj.get("links"), dict) else {}
    if links.get("url"):
        return str(links["url"])
    return None
