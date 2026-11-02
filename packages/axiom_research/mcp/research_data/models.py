from pydantic import BaseModel, ConfigDict, Field


class ResearchDataModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ZenodoRecord(ResearchDataModel):
    record_id: str
    concept_recid: str | None = None
    doi: str | None = None
    conceptdoi: str | None = None
    title: str | None = None
    publication_date: str | None = None
    version: str | None = None
    resource_type: str | None = None
    access_right: str | None = None
    license_id: str | None = None
    license_url: str | None = None
    files_count: int | None = None
    record_url: str | None = None
    evidence_kind: str = "dataset"
    limitations: list[str] = Field(
        default_factory=lambda: [
            "Zenodo deposit metadata only; file contents are not downloaded.",
            "Prefer DataCite to independently resolve the dataset PID.",
        ]
    )


class ZenodoSearchResult(ResearchDataModel):
    query: str
    count: int
    records: list[ZenodoRecord]


class DataCiteDoi(ResearchDataModel):
    doi: str
    url: str | None = None
    state: str | None = None
    publisher: str | None = None
    publication_year: int | None = None
    titles: list[str] = Field(default_factory=list)
    resource_type_general: str | None = None
    version: str | None = None
    rights_list: list[str] = Field(default_factory=list)
    client_id: str | None = None
    provider_id: str | None = None
    evidence_kind: str = "dataset_pid"
    limitations: list[str] = Field(
        default_factory=lambda: [
            "Independent PID/metadata resolve via DataCite; not the Zenodo deposit UI.",
        ]
    )
