from typing import Any
from urllib.parse import quote

from axiom_research.mcp.errors import McpRuntimeError
from axiom_research.mcp.research_data.models import DataCiteDoi
from axiom_research.mcp.upstream import UpstreamClient

DATACITE_DOIS = "https://api.datacite.org/dois"


class DataCiteClient:
    """Independent PID/metadata resolve. Verifier path; not Zenodo deposit API."""

    def __init__(self, upstream: UpstreamClient):
        self._upstream = upstream

    async def resolve_doi(self, doi: str) -> DataCiteDoi:
        cleaned = _normalize_doi(doi)
        if not cleaned:
            raise McpRuntimeError("VALIDATION", "doi must not be empty")
        url = f"{DATACITE_DOIS}/{quote(cleaned, safe='/')}"
        payload = await self._upstream.get_json(
            url,
            headers={"Accept": "application/vnd.api+json"},
        )
        if not isinstance(payload, dict) or not isinstance(payload.get("data"), dict):
            raise McpRuntimeError("VALIDATION", "DataCite returned unexpected payload")
        return _normalize_doi_record(payload["data"], fallback_doi=cleaned)


def _normalize_doi(doi: str) -> str:
    cleaned = doi.strip()
    for prefix in ("https://doi.org/", "http://doi.org/", "doi:"):
        if cleaned.lower().startswith(prefix):
            cleaned = cleaned[len(prefix) :]
            break
    return cleaned.strip()


def _normalize_doi_record(raw: dict[str, Any], *, fallback_doi: str) -> DataCiteDoi:
    attrs = raw.get("attributes") if isinstance(raw.get("attributes"), dict) else {}
    doi = str(attrs.get("doi") or raw.get("id") or fallback_doi)
    titles_raw = attrs.get("titles") if isinstance(attrs.get("titles"), list) else []
    titles = [
        str(item["title"])
        for item in titles_raw
        if isinstance(item, dict) and item.get("title")
    ]
    types = attrs.get("types") if isinstance(attrs.get("types"), dict) else {}
    rights = attrs.get("rightsList") if isinstance(attrs.get("rightsList"), list) else []
    rights_list = [
        str(item.get("rights") or item.get("rightsUri") or "")
        for item in rights
        if isinstance(item, dict)
    ]
    rights_list = [r for r in rights_list if r]
    year = attrs.get("publicationYear")
    publisher = attrs.get("publisher")
    if isinstance(publisher, dict):
        publisher_name = str(publisher.get("name") or "") or None
    else:
        publisher_name = str(publisher) if publisher else None
    return DataCiteDoi(
        doi=doi,
        url=str(attrs["url"]) if attrs.get("url") else f"https://doi.org/{doi}",
        state=str(attrs["state"]) if attrs.get("state") else None,
        publisher=publisher_name,
        publication_year=int(year) if isinstance(year, int) else None,
        titles=titles,
        resource_type_general=str(types["resourceTypeGeneral"])
        if types.get("resourceTypeGeneral")
        else None,
        version=str(attrs["version"]) if attrs.get("version") else None,
        rights_list=rights_list,
        client_id=str(raw["relationships"]["client"]["data"]["id"])
        if _client_id(raw)
        else None,
        provider_id=str(raw["relationships"]["provider"]["data"]["id"])
        if _provider_id(raw)
        else None,
    )


def _client_id(raw: dict[str, Any]) -> str | None:
    rel = raw.get("relationships") if isinstance(raw.get("relationships"), dict) else {}
    client = rel.get("client") if isinstance(rel.get("client"), dict) else {}
    data = client.get("data") if isinstance(client.get("data"), dict) else {}
    return str(data["id"]) if data.get("id") else None


def _provider_id(raw: dict[str, Any]) -> str | None:
    rel = raw.get("relationships") if isinstance(raw.get("relationships"), dict) else {}
    provider = rel.get("provider") if isinstance(rel.get("provider"), dict) else {}
    data = provider.get("data") if isinstance(provider.get("data"), dict) else {}
    return str(data["id"]) if data.get("id") else None
