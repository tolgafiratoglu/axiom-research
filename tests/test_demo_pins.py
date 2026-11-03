"""9.1 — pinned live identifiers for the solid-state battery canonical demo."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from axiom_research.demo.pins import (
    CANONICAL_QUESTION,
    CanonicalPins,
    load_canonical_pins,
    pins_path,
)


def test_canonical_pins_file_loads() -> None:
    path = pins_path()
    assert path.is_file()
    pins = load_canonical_pins()
    assert pins.question == CANONICAL_QUESTION
    assert pins.version == 1


def test_pins_cover_all_three_mcp_servers_and_providers() -> None:
    pins = load_canonical_pins()
    assert pins.literature.mcp_server == "mcp-literature"
    assert pins.materials_project.mcp_server == "mcp-materials"
    assert pins.pubchem.mcp_server == "mcp-materials"
    assert pins.zenodo.mcp_server == "mcp-research-data"
    assert pins.datacite.mcp_server == "mcp-research-data"

    assert pins.literature.doi == "10.1038/nmat2440"
    assert pins.literature.openalex_work_id.startswith("doi:")
    assert pins.materials_project.material_id == "mp-19017"
    assert pins.pubchem.cid == 66377
    assert pins.zenodo.record_id == "3233912"
    assert pins.zenodo.doi == pins.datacite.doi == "10.5281/zenodo.3233912"
    assert "zenodo_get_record" in pins.zenodo.tools
    assert "datacite_resolve_doi" in pins.datacite.tools
    assert pins.zenodo.tools != pins.datacite.tools


def test_source_refs_list_is_complete() -> None:
    pins = load_canonical_pins()
    refs = set(pins.source_refs)
    assert "doi:10.1038/nmat2440" in refs
    assert "materials-project:mp-19017" in refs
    assert "pubchem:cid:66377" in refs
    assert "zenodo:3233912" in refs
    assert "doi:10.5281/zenodo.3233912" in refs


def test_rejects_fabricated_literature_doi() -> None:
    pins = load_canonical_pins()
    payload = pins.model_dump()
    payload["literature"]["doi"] = "10.9999/axiom.fabricated-doi-001"
    with pytest.raises(ValidationError):
        CanonicalPins.model_validate(payload)
