from typing import Any

from axiom_research.mcp.errors import McpRuntimeError
from axiom_research.mcp.materials.models import (
    MaterialsProjectRecord,
    MaterialsProjectSearchResult,
)
from axiom_research.mcp.upstream import UpstreamClient

MP_SUMMARY = "https://api.materialsproject.org/materials/summary/"
_FIELDS = (
    "material_id,formula_pretty,band_gap,formation_energy_per_atom,"
    "energy_above_hull,is_stable,symmetry"
)


class MaterialsProjectClient:
    """Computed crystal properties from Materials Project. Never experimental."""

    def __init__(self, upstream: UpstreamClient, *, api_key: str):
        if not api_key:
            raise McpRuntimeError(
                "UNAUTHORIZED",
                "MP_API_KEY missing; add it to SECRETS_ENV_PATH",
            )
        self._upstream = upstream
        self._headers = {"X-API-KEY": api_key}

    async def get_material(self, material_id: str) -> MaterialsProjectRecord:
        cleaned = _normalize_material_id(material_id)
        if not cleaned:
            raise McpRuntimeError("VALIDATION", "material_id must not be empty")
        payload = await self._upstream.get_json(
            MP_SUMMARY,
            params={"material_ids": cleaned, "_fields": _FIELDS, "_limit": 1},
            headers=self._headers,
        )
        rows = _rows(payload)
        if not rows:
            raise McpRuntimeError("NOT_FOUND", f"Materials Project id not found: {cleaned}")
        return _normalize_record(rows[0])

    async def search_by_formula(
        self,
        formula: str,
        *,
        limit: int = 5,
    ) -> MaterialsProjectSearchResult:
        cleaned = formula.strip()
        if not cleaned:
            raise McpRuntimeError("VALIDATION", "formula must not be empty")
        if limit < 1 or limit > 25:
            raise McpRuntimeError("VALIDATION", "limit must be between 1 and 25")
        payload = await self._upstream.get_json(
            MP_SUMMARY,
            params={"formula": cleaned, "_fields": _FIELDS, "_limit": limit},
            headers=self._headers,
        )
        rows = _rows(payload)
        materials = [_normalize_record(row) for row in rows]
        meta = payload.get("meta") if isinstance(payload, dict) else {}
        count = int(meta.get("total_doc") or len(materials)) if isinstance(meta, dict) else len(materials)
        return MaterialsProjectSearchResult(formula=cleaned, count=count, materials=materials)


def _normalize_material_id(material_id: str) -> str:
    cleaned = material_id.strip()
    if cleaned.lower().startswith("materials-project:"):
        cleaned = cleaned.split(":", 1)[1]
    return cleaned.strip()


def _rows(payload: Any) -> list[dict[str, Any]]:
    if not isinstance(payload, dict):
        raise McpRuntimeError("VALIDATION", "Materials Project returned unexpected payload")
    data = payload.get("data")
    if not isinstance(data, list):
        raise McpRuntimeError("VALIDATION", "Materials Project data must be a list")
    return [row for row in data if isinstance(row, dict)]


def _normalize_record(raw: dict[str, Any]) -> MaterialsProjectRecord:
    material_id = str(raw.get("material_id") or "")
    if not material_id:
        raise McpRuntimeError("VALIDATION", "Materials Project row missing material_id")
    symmetry = raw.get("symmetry") if isinstance(raw.get("symmetry"), dict) else {}
    return MaterialsProjectRecord(
        material_id=material_id,
        formula_pretty=str(raw["formula_pretty"]) if raw.get("formula_pretty") else None,
        band_gap_ev=_float_or_none(raw.get("band_gap")),
        formation_energy_per_atom_ev=_float_or_none(raw.get("formation_energy_per_atom")),
        energy_above_hull_ev=_float_or_none(raw.get("energy_above_hull")),
        is_stable=bool(raw["is_stable"]) if isinstance(raw.get("is_stable"), bool) else None,
        spacegroup_symbol=str(symmetry["symbol"]) if symmetry.get("symbol") else None,
    )


def _float_or_none(value: Any) -> float | None:
    if isinstance(value, (int, float)):
        return float(value)
    return None
