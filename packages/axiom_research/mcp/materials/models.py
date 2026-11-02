from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class MaterialsModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class MaterialsProjectRecord(MaterialsModel):
    material_id: str
    formula_pretty: str | None = None
    band_gap_ev: float | None = None
    formation_energy_per_atom_ev: float | None = None
    energy_above_hull_ev: float | None = None
    is_stable: bool | None = None
    spacegroup_symbol: str | None = None
    evidence_kind: Literal["computed_property"] = "computed_property"
    method: str = "DFT as recorded by Materials Project summary"
    units: dict[str, str] = Field(
        default_factory=lambda: {
            "band_gap": "eV",
            "formation_energy_per_atom": "eV/atom",
            "energy_above_hull": "eV/atom",
        }
    )
    limitations: list[str] = Field(
        default_factory=lambda: [
            "Values are computed (DFT), not experimental measurements.",
            "A computed property is not commercial readiness or lab validation.",
        ]
    )


class MaterialsProjectSearchResult(MaterialsModel):
    formula: str
    count: int
    materials: list[MaterialsProjectRecord]


class PubChemCompound(MaterialsModel):
    cid: int
    molecular_formula: str | None = None
    molecular_weight: float | None = None
    iupac_name: str | None = None
    inchikey: str | None = None
    canonical_smiles: str | None = None
    title: str | None = None
    evidence_kind: Literal["compound_metadata"] = "compound_metadata"
    method: str = "PubChem PUG REST compound property table"
    limitations: list[str] = Field(
        default_factory=lambda: [
            "Compound registry metadata; not a Materials Project computed crystal property.",
        ]
    )
