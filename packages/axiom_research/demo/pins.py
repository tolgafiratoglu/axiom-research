"""Pinned live identifiers for the solid-state battery canonical demo (9.1)."""

from __future__ import annotations

import json
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

CANONICAL_QUESTION = (
    "Can solid-state batteries realistically replace conventional lithium-ion batteries? "
    "What do published studies, computed materials data, and deposited research datasets "
    "actually support?"
)


class _PinBase(BaseModel):
    model_config = ConfigDict(extra="forbid")

    provider: str
    mcp_server: str
    tools: list[str] = Field(min_length=1)
    why: str


class LiteraturePin(_PinBase):
    doi: str
    openalex_work_id: str
    title_hint: str | None = None

    @field_validator("doi")
    @classmethod
    def _real_doi(cls, value: str) -> str:
        text = value.strip()
        if not text or text.startswith("10.9999/") or "fabricated" in text.lower():
            raise ValueError("literature DOI must be a pinned live identifier")
        return text


class MaterialsProjectPin(_PinBase):
    material_id: str
    formula_hint: str | None = None
    evidence_kind: str = "computed_property"

    @field_validator("material_id")
    @classmethod
    def _mp_id(cls, value: str) -> str:
        text = value.strip()
        if not text.startswith("mp-"):
            raise ValueError("materials_project material_id must look like mp-…")
        return text


class PubChemPin(_PinBase):
    cid: int
    name_hint: str | None = None
    formula_hint: str | None = None

    @field_validator("cid")
    @classmethod
    def _positive_cid(cls, value: int) -> int:
        if value <= 0:
            raise ValueError("pubchem cid must be positive")
        return value


class ZenodoPin(_PinBase):
    record_id: str
    doi: str


class DataCitePin(_PinBase):
    doi: str


class CanonicalPins(BaseModel):
    model_config = ConfigDict(extra="forbid")

    version: int = 1
    question: str
    purpose: str
    literature: LiteraturePin
    materials_project: MaterialsProjectPin
    pubchem: PubChemPin
    zenodo: ZenodoPin
    datacite: DataCitePin
    source_refs: list[str] = Field(min_length=5)

    @model_validator(mode="after")
    def _demo_invariants(self) -> CanonicalPins:
        if self.question.strip() != CANONICAL_QUESTION:
            raise ValueError("question must match the ReadMe canonical demo question")
        if self.zenodo.doi != self.datacite.doi:
            raise ValueError(
                "zenodo.doi and datacite.doi must be the same PID "
                "(distinct fetch tools; same identifier — RoadMap 9.3)"
            )
        if self.zenodo.tools == self.datacite.tools:
            raise ValueError("Zenodo and DataCite must use different MCP tools")
        required_servers = {
            "mcp-literature",
            "mcp-materials",
            "mcp-research-data",
        }
        present = {
            self.literature.mcp_server,
            self.materials_project.mcp_server,
            self.pubchem.mcp_server,
            self.zenodo.mcp_server,
            self.datacite.mcp_server,
        }
        if not required_servers <= present:
            raise ValueError(f"pins must cover MCP servers {sorted(required_servers)}")
        return self


def pins_path(explicit: Path | None = None) -> Path:
    if explicit is not None:
        return explicit
    # packages/axiom_research/demo/pins.py → repo/demo/canonical_pins.json
    return Path(__file__).resolve().parents[3] / "demo" / "canonical_pins.json"


def load_canonical_pins(path: Path | None = None) -> CanonicalPins:
    raw = json.loads(pins_path(path).read_text(encoding="utf-8"))
    return CanonicalPins.model_validate(raw)
