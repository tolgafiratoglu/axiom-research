"""Metadata-only policy. No PDF/full-text bulk download, no vector index."""

from axiom_research.mcp.errors import McpRuntimeError

_FORBIDDEN_URL_MARKERS = (".pdf", "/pdf/", "fulltext", "full-text", "/download")
_FORBIDDEN_INTENTS = frozenset(
    {
        "pdf",
        "full_text",
        "abstract_bulk",
        "embed",
        "vector_index",
        "vectorize",
    }
)


def assert_metadata_only(*, url: str | None = None, intent: str | None = None) -> None:
    if intent and intent.strip().lower() in _FORBIDDEN_INTENTS:
        raise McpRuntimeError(
            "POLICY",
            "metadata only: PDF, bulk abstract, and vector-index intents are forbidden",
        )
    if url:
        lowered = url.lower()
        if any(marker in lowered for marker in _FORBIDDEN_URL_MARKERS):
            raise McpRuntimeError(
                "POLICY",
                "metadata only: PDF or full-text download URLs are forbidden",
            )
