from pydantic import BaseModel, ConfigDict, Field


class LiteratureModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class OpenAlexWorkSummary(LiteratureModel):
    openalex_id: str
    doi: str | None = None
    title: str | None = None
    publication_year: int | None = None
    type: str | None = None
    cited_by_count: int | None = None
    referenced_works: list[str] = Field(default_factory=list)
    related_works: list[str] = Field(default_factory=list)
    ids: dict[str, str] = Field(default_factory=dict)
    landing_page_url: str | None = None
    is_preprint: bool = False


class OpenAlexSearchResult(LiteratureModel):
    query: str
    count: int
    works: list[OpenAlexWorkSummary]


class CrossrefWork(LiteratureModel):
    doi: str
    title: str | None = None
    type: str | None = None
    container_title: str | None = None
    published: str | None = None
    publisher: str | None = None
    is_referenced_by_count: int | None = None
    url: str | None = None
    issn: list[str] = Field(default_factory=list)
    member: str | None = None


class ArxivRecord(LiteratureModel):
    arxiv_id: str
    title: str | None = None
    published: str | None = None
    updated: str | None = None
    primary_category: str | None = None
    doi: str | None = None
    journal_ref: str | None = None
    comment: str | None = None
    abs_url: str | None = None
    is_preprint: bool = True
    later_publication_signal: bool = False
    later_publication_note: str | None = None
