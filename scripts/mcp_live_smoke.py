#!/usr/bin/env python3
"""Manual live smoke for scientific providers + MCP /health.

Not for CI. Hits live OpenAlex, Crossref, arXiv, Materials Project, PubChem,
Zenodo, and DataCite once each, then GET /health on the three Compose MCP ports.

Usage (operator):
  docker compose up -d --build mcp-literature mcp-materials mcp-research-data
  # MP_API_KEY in ~/.config/rag/.env for Materials Project
  .venv/bin/python scripts/mcp_live_smoke.py
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

import httpx2

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "packages"))

from axiom_research.mcp.literature.arxiv import ArxivClient  # noqa: E402
from axiom_research.mcp.literature.crossref import CrossrefClient  # noqa: E402
from axiom_research.mcp.literature.openalex import OpenAlexClient  # noqa: E402
from axiom_research.mcp.materials.materials_project import MaterialsProjectClient  # noqa: E402
from axiom_research.mcp.materials.pubchem import PubChemClient  # noqa: E402
from axiom_research.mcp.research_data.datacite import DataCiteClient  # noqa: E402
from axiom_research.mcp.research_data.zenodo import ZenodoClient  # noqa: E402
from axiom_research.mcp.upstream import UpstreamClient  # noqa: E402
from axiom_research.settings import load_mp_api_key, settings  # noqa: E402

HEALTH_URLS = (
    "http://127.0.0.1:8210/health",
    "http://127.0.0.1:8211/health",
    "http://127.0.0.1:8212/health",
)


async def main() -> int:
    async with httpx2.AsyncClient(timeout=30.0) as http:
        for url in HEALTH_URLS:
            response = await http.get(url)
            response.raise_for_status()
            print(f"health ok: {url} -> {response.json()}")

        upstream = UpstreamClient(http)
        openalex = await OpenAlexClient(upstream).search_works("solid state battery", per_page=1)
        print(f"openalex: {openalex.count} hits, first={openalex.works[0].openalex_id if openalex.works else None}")

        crossref = await CrossrefClient(upstream).resolve_doi("10.7717/peerj.4375")
        print(f"crossref: {crossref.doi} type={crossref.type}")

        arxiv = await ArxivClient(upstream).get_preprint("2101.00001")
        print(f"arxiv: {arxiv.arxiv_id} later={arxiv.later_publication_signal}")

        mp_key = load_mp_api_key(settings.secrets_env_path)
        if not mp_key:
            print("materials_project: SKIP (MP_API_KEY missing in SECRETS_ENV_PATH)")
        else:
            mp = await MaterialsProjectClient(upstream, api_key=mp_key).get_material("mp-149")
            print(f"materials_project: {mp.material_id} kind={mp.evidence_kind}")

        pubchem = await PubChemClient(upstream).get_by_cid(2244)
        print(f"pubchem: cid={pubchem.cid} formula={pubchem.molecular_formula}")

        zenodo = await ZenodoClient(upstream).search_records("battery", size=1)
        print(f"zenodo: {zenodo.count} hits")

        if zenodo.records and zenodo.records[0].doi:
            doi = zenodo.records[0].doi
        else:
            doi = "10.5281/zenodo.3233912"
        datacite = await DataCiteClient(upstream).resolve_doi(doi)
        print(f"datacite: {datacite.doi} type={datacite.resource_type_general}")

    print("live smoke finished")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
