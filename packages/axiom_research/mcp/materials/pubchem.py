from typing import Any
from urllib.parse import quote

from axiom_research.mcp.errors import McpRuntimeError
from axiom_research.mcp.materials.models import PubChemCompound
from axiom_research.mcp.upstream import UpstreamClient

PUG = "https://pubchem.ncbi.nlm.nih.gov/rest/pug"
_PROPERTIES = "MolecularFormula,MolecularWeight,IUPACName,InChIKey,CanonicalSMILES,Title"


class PubChemClient:
    """Compound registry metadata via PUG REST. Not computed crystal properties."""

    def __init__(self, upstream: UpstreamClient):
        self._upstream = upstream

    async def get_by_cid(self, cid: int) -> PubChemCompound:
        if cid < 1:
            raise McpRuntimeError("VALIDATION", "cid must be a positive integer")
        url = f"{PUG}/compound/cid/{cid}/property/{_PROPERTIES}/JSON"
        payload = await self._upstream.get_json(url)
        return _normalize_property_table(payload, expected_cid=cid)

    async def get_by_name(self, name: str) -> PubChemCompound:
        cleaned = name.strip()
        if not cleaned:
            raise McpRuntimeError("VALIDATION", "name must not be empty")
        url = f"{PUG}/compound/name/{quote(cleaned)}/property/{_PROPERTIES}/JSON"
        payload = await self._upstream.get_json(url)
        return _normalize_property_table(payload, expected_cid=None)


def _normalize_property_table(
    payload: Any,
    *,
    expected_cid: int | None,
) -> PubChemCompound:
    if not isinstance(payload, dict):
        raise McpRuntimeError("VALIDATION", "PubChem returned unexpected payload")
    table = payload.get("PropertyTable")
    if not isinstance(table, dict):
        raise McpRuntimeError("VALIDATION", "PubChem PropertyTable missing")
    props = table.get("Properties")
    if not isinstance(props, list) or not props or not isinstance(props[0], dict):
        raise McpRuntimeError("NOT_FOUND", "PubChem compound not found")
    row = props[0]
    cid_raw = row.get("CID")
    if not isinstance(cid_raw, int):
        raise McpRuntimeError("VALIDATION", "PubChem row missing CID")
    if expected_cid is not None and cid_raw != expected_cid:
        raise McpRuntimeError("VALIDATION", "PubChem CID mismatch")
    return PubChemCompound(
        cid=cid_raw,
        molecular_formula=str(row["MolecularFormula"]) if row.get("MolecularFormula") else None,
        molecular_weight=_as_float(row.get("MolecularWeight")),
        iupac_name=str(row["IUPACName"]) if row.get("IUPACName") else None,
        inchikey=str(row["InChIKey"]) if row.get("InChIKey") else None,
        canonical_smiles=str(row["CanonicalSMILES"]) if row.get("CanonicalSMILES") else None,
        title=str(row["Title"]) if row.get("Title") else None,
    )


def _as_float(value: Any) -> float | None:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str) and value.strip():
        try:
            return float(value)
        except ValueError:
            return None
    return None
