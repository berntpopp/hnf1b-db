"""Experimental HNF1B structure (PDB 2H8R) and per-residue distance to DNA.

The backend owns the single copy of the structure file: the frontend 3D viewer
loads it from ``GET /reference/genes/HNF1B/structure`` and the DNA-distance
analysis reads ``.../structure/dna-distances``, both computed from this file.
"""

import math
from functools import cache
from pathlib import Path

GENE = "HNF1B"
PDB_ID = "2H8R"
STRUCTURE_FILE = Path(__file__).parent / "structures" / "2h8r.cif"
DISTANCE_METHOD = (
    "Minimum distance between any non-hydrogen atom of the residue "
    "(either protein chain) and any non-hydrogen DNA atom"
)

_DNA_RESIDUES = {"DA", "DT", "DG", "DC"}
_AMINO_ACIDS = {
    "ALA", "ARG", "ASN", "ASP", "CYS", "GLN", "GLU", "GLY", "HIS", "ILE",
    "LEU", "LYS", "MET", "PHE", "PRO", "SER", "THR", "TRP", "TYR", "VAL",
}  # fmt: skip


def _atom_sites(text: str) -> list[dict[str, str]]:
    """Rows of the mmCIF ``_atom_site`` loop as column -> value dicts."""
    lines = text.splitlines()
    columns: list[str] = []
    rows: list[dict[str, str]] = []
    for line in lines:
        if line.startswith("_atom_site."):
            columns.append(line.split(".", 1)[1].strip())
        elif columns and line.startswith(("ATOM", "HETATM")):
            rows.append(dict(zip(columns, line.split())))
        elif rows:
            break
    return rows


@cache
def residue_dna_distances() -> dict[int, float]:
    """Closest heavy-atom distance (Å) from each resolved residue to the DNA.

    Residues are keyed by ``auth_seq_id``, which matches UniProt P35680
    numbering. 2H8R has one model and no alternate locations, so a plain read
    of the atom table gives the same values as NGL in the 3D viewer.
    """
    atoms = _atom_sites(STRUCTURE_FILE.read_text())
    heavy = [a for a in atoms if a["type_symbol"] != "H"]

    def xyz(atom: dict[str, str]) -> tuple[float, float, float]:
        return (float(atom["Cartn_x"]), float(atom["Cartn_y"]), float(atom["Cartn_z"]))

    dna = [xyz(a) for a in heavy if a["auth_comp_id"] in _DNA_RESIDUES]
    residues: dict[int, list[tuple[float, float, float]]] = {}
    for atom in heavy:
        if atom["auth_comp_id"] in _AMINO_ACIDS:
            residues.setdefault(int(atom["auth_seq_id"]), []).append(xyz(atom))

    return {
        number: round(min(math.dist(p, q) for p in points for q in dna), 3)
        for number, points in sorted(residues.items())
    }
