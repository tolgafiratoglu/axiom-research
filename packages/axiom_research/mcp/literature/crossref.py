from typing import Any
from urllib.parse import quote

from axiom_research.mcp.errors import McpRuntimeError
from axiom_research.mcp.literature.models import CrossrefWork
from axiom_research.mcp.upstream import UpstreamClient

CROSSREF_WORKS = "https://api.crossref.org/works"


class CrossrefClient:
    """DOI registry metadata resolve. Not a discovery/search index."""

    def __init__(self, upstream: UpstreamClient, *, mailto: str | None = None):
        self._upstream = upstream
        self._mailto = mailto

    async def resolve_doi(self, doi: str) -> CrossrefWork:
        cleaned = _normalize_doi(doi)
        if not cleaned:
            raise McpRuntimeError("VALIDATION", "doi must not be empty")
        url = f"{CROSSREF_WORKS}/{quote(cleaned, safe='/')}"
        params: dict[str, Any] = {}
        if self._mailto:
            params["mailto"] = self._mailto
        payload = await self._upstream.get_json(url, params=params or None)
        if not isinstance(payload, dict) or not isinstance(payload.get("message"), dict):
            raise McpRuntimeError("VALIDATION", "Crossref returned unexpected payload")
        return _normalize_work(payload["message"], fallback_doi=cleaned)


def _normalize_doi(doi: str) -> str:
    cleaned = doi.strip()
    for prefix in ("https://doi.org/", "http://doi.org/", "doi:"):
        if cleaned.lower().startswith(prefix):
            cleaned = cleaned[len(prefix) :]
            break
    return cleaned.strip()


def _normalize_work(raw: dict[str, Any], *, fallback_doi: str) -> CrossrefWork:
    doi = str(raw.get("DOI") or fallback_doi)
    titles = raw.get("title") if isinstance(raw.get("title"), list) else []
    containers = (
        raw.get("container-title") if isinstance(raw.get("container-title"), list) else []
    )
    issn = [str(x) for x in (raw.get("ISSN") or []) if x]
    published = _format_date_parts(raw.get("published-print") or raw.get("published-online"))
    return CrossrefWork(
        doi=doi,
        title=str(titles[0]) if titles else None,
        type=str(raw["type"]) if raw.get("type") else None,
        container_title=str(containers[0]) if containers else None,
        published=published,
        publisher=str(raw["publisher"]) if raw.get("publisher") else None,
        is_referenced_by_count=int(raw["is-referenced-by-count"])
        if isinstance(raw.get("is-referenced-by-count"), int)
        else None,
        url=str(raw["URL"]) if raw.get("URL") else f"https://doi.org/{doi}",
        issn=issn,
        member=str(raw["member"]) if raw.get("member") else None,
    )


def _format_date_parts(block: Any) -> str | None:
    if not isinstance(block, dict):
        return None
    parts = block.get("date-parts")
    if not isinstance(parts, list) or not parts or not isinstance(parts[0], list):
        return None
    values = [str(x) for x in parts[0] if x is not None]
    return "-".join(values) if values else None
