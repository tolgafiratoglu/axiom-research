import xml.etree.ElementTree as ET
from typing import Any

from axiom_research.mcp.errors import McpRuntimeError
from axiom_research.mcp.literature.models import ArxivRecord
from axiom_research.mcp.upstream import UpstreamClient

ARXIV_API = "https://export.arxiv.org/api/query"
ATOM = "{http://www.w3.org/2005/Atom}"
ARXIV_NS = "{http://arxiv.org/schemas/atom}"


class ArxivClient:
    """Preprint metadata and later-publication signals (journal_ref / DOI)."""

    def __init__(self, upstream: UpstreamClient):
        self._upstream = upstream

    async def get_preprint(self, arxiv_id: str) -> ArxivRecord:
        cleaned = _normalize_arxiv_id(arxiv_id)
        if not cleaned:
            raise McpRuntimeError("VALIDATION", "arxiv_id must not be empty")
        text = await self._upstream.get_text(
            ARXIV_API,
            params={"id_list": cleaned, "max_results": 1},
        )
        return _parse_atom(text, expected_id=cleaned)


def _normalize_arxiv_id(arxiv_id: str) -> str:
    cleaned = arxiv_id.strip()
    for prefix in ("arxiv:", "https://arxiv.org/abs/", "http://arxiv.org/abs/"):
        if cleaned.lower().startswith(prefix):
            cleaned = cleaned[len(prefix) :]
            break
    return cleaned.strip()


def _parse_atom(text: str, *, expected_id: str) -> ArxivRecord:
    try:
        root = ET.fromstring(text)
    except ET.ParseError as exc:
        raise McpRuntimeError("VALIDATION", "arXiv returned invalid Atom XML") from exc

    entry = root.find(f"{ATOM}entry")
    if entry is None:
        raise McpRuntimeError("NOT_FOUND", f"arXiv entry not found for {expected_id}")

    raw_id = _text(entry.find(f"{ATOM}id")) or ""
    arxiv_id = raw_id.rsplit("/abs/", 1)[-1] if "/abs/" in raw_id else expected_id
    title = _collapse(_text(entry.find(f"{ATOM}title")))
    published = _text(entry.find(f"{ATOM}published"))
    updated = _text(entry.find(f"{ATOM}updated"))
    primary = entry.find(f"{ARXIV_NS}primary_category")
    primary_category = primary.get("term") if primary is not None else None
    doi = _text(entry.find(f"{ARXIV_NS}doi"))
    journal_ref = _text(entry.find(f"{ARXIV_NS}journal_ref"))
    comment = _text(entry.find(f"{ARXIV_NS}comment"))
    later = bool(doi or journal_ref)
    note = None
    if later:
        note = (
            "arXiv record carries journal_ref and/or DOI; treat as preprint with a "
            "possible later publication — not peer-reviewed status by itself."
        )
    else:
        note = "No journal_ref/DOI on arXiv entry; still a preprint, not peer-reviewed."

    return ArxivRecord(
        arxiv_id=arxiv_id,
        title=title,
        published=published,
        updated=updated,
        primary_category=primary_category,
        doi=doi,
        journal_ref=journal_ref,
        comment=comment,
        abs_url=f"https://arxiv.org/abs/{arxiv_id}",
        is_preprint=True,
        later_publication_signal=later,
        later_publication_note=note,
    )


def _text(node: Any) -> str | None:
    if node is None or node.text is None:
        return None
    value = node.text.strip()
    return value or None


def _collapse(value: str | None) -> str | None:
    if value is None:
        return None
    return " ".join(value.split())
