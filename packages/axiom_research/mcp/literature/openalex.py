from typing import Any

from axiom_research.mcp.errors import McpRuntimeError
from axiom_research.mcp.literature.models import OpenAlexSearchResult, OpenAlexWorkSummary
from axiom_research.mcp.upstream import UpstreamClient

OPENALEX_WORKS = "https://api.openalex.org/works"
_SELECT = (
    "id,doi,title,publication_year,type,cited_by_count,"
    "referenced_works,related_works,ids,primary_location"
)
_PREPRINT_TYPES = frozenset({"preprint", "posted-content"})


class OpenAlexClient:
    """Discovery + citation graph + identifiers. Not DOI registry of record."""

    def __init__(self, upstream: UpstreamClient, *, mailto: str | None = None):
        self._upstream = upstream
        self._mailto = mailto

    async def search_works(self, query: str, *, per_page: int = 5) -> OpenAlexSearchResult:
        if not query.strip():
            raise McpRuntimeError("VALIDATION", "query must not be empty")
        if per_page < 1 or per_page > 25:
            raise McpRuntimeError("VALIDATION", "per_page must be between 1 and 25")
        params: dict[str, Any] = {
            "search": query.strip(),
            "per_page": per_page,
            "select": _SELECT,
        }
        if self._mailto:
            params["mailto"] = self._mailto
        payload = await self._upstream.get_json(OPENALEX_WORKS, params=params)
        if not isinstance(payload, dict):
            raise McpRuntimeError("VALIDATION", "OpenAlex returned unexpected payload")
        results = payload.get("results") or []
        if not isinstance(results, list):
            raise McpRuntimeError("VALIDATION", "OpenAlex results must be a list")
        works = [_normalize_work(item) for item in results if isinstance(item, dict)]
        meta = payload.get("meta") if isinstance(payload.get("meta"), dict) else {}
        count = int(meta.get("count") or len(works))
        return OpenAlexSearchResult(query=query.strip(), count=count, works=works)

    async def get_work(self, work_id: str) -> OpenAlexWorkSummary:
        cleaned = work_id.strip()
        if not cleaned:
            raise McpRuntimeError("VALIDATION", "work_id must not be empty")
        if cleaned.startswith("http"):
            path = cleaned
        elif cleaned.upper().startswith("W"):
            path = f"{OPENALEX_WORKS}/{cleaned}"
        elif cleaned.lower().startswith("doi:"):
            path = f"{OPENALEX_WORKS}/{cleaned}"
        else:
            path = f"{OPENALEX_WORKS}/{cleaned}"
        params: dict[str, Any] = {"select": _SELECT}
        if self._mailto:
            params["mailto"] = self._mailto
        payload = await self._upstream.get_json(path, params=params)
        if not isinstance(payload, dict):
            raise McpRuntimeError("VALIDATION", "OpenAlex returned unexpected payload")
        return _normalize_work(payload)


def _normalize_work(raw: dict[str, Any]) -> OpenAlexWorkSummary:
    openalex_id = str(raw.get("id") or "")
    if not openalex_id:
        raise McpRuntimeError("VALIDATION", "OpenAlex work missing id")
    work_type = raw.get("type")
    type_str = str(work_type) if work_type is not None else None
    primary = raw.get("primary_location") if isinstance(raw.get("primary_location"), dict) else {}
    ids_raw = raw.get("ids") if isinstance(raw.get("ids"), dict) else {}
    ids = {str(k): str(v) for k, v in ids_raw.items() if v is not None}
    referenced = [str(x) for x in (raw.get("referenced_works") or [])[:20] if x]
    related = [str(x) for x in (raw.get("related_works") or [])[:10] if x]
    year = raw.get("publication_year")
    return OpenAlexWorkSummary(
        openalex_id=openalex_id,
        doi=str(raw["doi"]) if raw.get("doi") else None,
        title=str(raw["title"]) if raw.get("title") else None,
        publication_year=int(year) if isinstance(year, int) else None,
        type=type_str,
        cited_by_count=int(raw["cited_by_count"])
        if isinstance(raw.get("cited_by_count"), int)
        else None,
        referenced_works=referenced,
        related_works=related,
        ids=ids,
        landing_page_url=str(primary["landing_page_url"])
        if primary.get("landing_page_url")
        else None,
        is_preprint=bool(type_str and type_str.lower() in _PREPRINT_TYPES),
    )
