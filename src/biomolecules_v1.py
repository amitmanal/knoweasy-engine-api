from __future__ import annotations

from typing import Any, Dict, List, Optional


def _lc(s: str) -> str:
    return (s or "").strip().lower()


def _normalize_spaces(s: str) -> str:
    return " ".join((s or "").split())


def _has_any(text: str, words: List[str]) -> bool:
    t = _lc(text)
    return any(w in t for w in words)


# -----------------------------
# Deterministic knowledge base
# -----------------------------
# Written as general chemistry/biology facts (NCERT/exam-standard),
# not copied from proprietary coaching materials.

_CARBS: Dict[str, Dict[str, Any]] = {
    "glucose": {
        "aliases": ["glucose", "d-glucose"],
        "type": "MONOSACCHARIDE (ALDOHEXOSE)",
        "reducing": True,
        "notes": "Common blood sugar; forms glucosidic linkages in polysaccharides.",
        "tests": "Gives positive Fehling's/Tollens' (reducing sugar).",
    },
    "fructose": {
        "aliases": ["fructose", "d-fructose"],
        "type": "MONOSACCHARIDE (KETOHEXOSE)",
        "reducing": True,  # via tautomerization in alkaline medium
        "notes": "Fruit sugar; ketose but behaves as reducing sugar in alkaline tests.",
        "tests": "Acts as reducing sugar in Fehling's/Tollens' due to tautomerization.",
    },
    "sucrose": {
        "aliases": ["sucrose", "cane sugar"],
        "type": "DISACCHARIDE",
        "reducing": False,
        "notes": "Non-reducing because both anomeric carbons are involved in glycosidic linkage.",
        "tests": "Does not give Fehling's/Tollens' unless hydrolyzed.",
    },
    "maltose": {
        "aliases": ["maltose"],
        "type": "DISACCHARIDE",
        "reducing": True,
        "notes": "Reducing disaccharide; has a free anomeric carbon.",
        "tests": "Gives positive Fehling's/Tollens' (reducing).",
    },
    "lactose": {
        "aliases": ["lactose"],
        "type": "DISACCHARIDE",
        "reducing": True,
        "notes": "Milk sugar; reducing disaccharide.",
        "tests": "Gives positive Fehling's/Tollens'.",
    },
    "starch": {
        "aliases": ["starch"],
        "type": "POLYSACCHARIDE",
        "reducing": False,  # treated as non-reducing in exam context
        "notes": "Storage polysaccharide in plants; gives blue color with iodine.",
        "tests": "Iodine test: blue color.",
    },
    "cellulose": {
        "aliases": ["cellulose"],
        "type": "POLYSACCHARIDE",
        "reducing": False,  # exam-safe
        "notes": "Structural polysaccharide in plants; not digested by humans.",
        "tests": "Does not give iodine blue like starch (exam-level distinction).",
    },
    "glycogen": {
        "aliases": ["glycogen"],
        "type": "POLYSACCHARIDE",
        "reducing": False,  # exam-safe
        "notes": "Storage polysaccharide in animals; highly branched.",
        "tests": "Iodine test: reddish-brown (exam-level).",
    },
}

_VITAMINS: Dict[str, Dict[str, Any]] = {
    "vitamin_a": {
        "aliases": ["vitamin a", "retinol"],
        "solubility": "FAT_SOLUBLE",
        "deficiency": "Night blindness (nyctalopia), xerophthalmia (exam standard).",
    },
    "vitamin_b1": {
        "aliases": ["vitamin b1", "thiamine"],
        "solubility": "WATER_SOLUBLE",
        "deficiency": "Beriberi.",
    },
    "vitamin_b2": {
        "aliases": ["vitamin b2", "riboflavin"],
        "solubility": "WATER_SOLUBLE",
        "deficiency": "Cheilosis, glossitis (exam standard).",
    },
    "vitamin_b3": {
        "aliases": ["vitamin b3", "niacin"],
        "solubility": "WATER_SOLUBLE",
        "deficiency": "Pellagra (3 D's: dermatitis, diarrhea, dementia).",
    },
    "vitamin_b6": {
        "aliases": ["vitamin b6", "pyridoxine"],
        "solubility": "WATER_SOLUBLE",
        "deficiency": "Dermatitis, anemia (exam standard).",
    },
    "vitamin_b12": {
        "aliases": ["vitamin b12", "cobalamin"],
        "solubility": "WATER_SOLUBLE",
        "deficiency": "Pernicious anemia.",
    },
    "vitamin_c": {
        "aliases": ["vitamin c", "ascorbic acid"],
        "solubility": "WATER_SOLUBLE",
        "deficiency": "Scurvy (bleeding gums, poor wound healing).",
    },
    "vitamin_d": {
        "aliases": ["vitamin d", "calciferol"],
        "solubility": "FAT_SOLUBLE",
        "deficiency": "Rickets (children), osteomalacia (adults).",
    },
    "vitamin_e": {
        "aliases": ["vitamin e", "tocopherol"],
        "solubility": "FAT_SOLUBLE",
        "deficiency": "Reproductive issues (exam standard, simplified).",
    },
    "vitamin_k": {
        "aliases": ["vitamin k"],
        "solubility": "FAT_SOLUBLE",
        "deficiency": "Delayed blood clotting (hemorrhage).",
    },
}

_NUCLEIC_ACIDS: Dict[str, str] = {
    "dna_vs_rna": (
        "DNA vs RNA: DNA usually has deoxyribose sugar and bases A, G, C, T; "
        "RNA has ribose sugar and bases A, G, C, U. DNA is typically double-stranded; RNA is typically single-stranded (exam standard)."
    ),
    "nucleoside_vs_nucleotide": (
        "Nucleoside = sugar + base. Nucleotide = nucleoside + phosphate group(s)."
    ),
}

_PROTEINS: Dict[str, str] = {
    "peptide_bond": "Peptide bond is an amide linkage (–CO–NH–) formed between the –COOH group of one amino acid and –NH2 group of another.",
    "structure_levels": (
        "Protein structure: Primary (sequence), Secondary (α-helix/β-sheet via H-bonding), "
        "Tertiary (3D folding), Quaternary (association of subunits)."
    ),
    "enzymes": "Enzymes are biological catalysts (mostly proteins) with high specificity; activity depends on pH and temperature.",
}


# Reverse alias map
_ALIAS_MAP: Dict[str, Tuple[str, str]] = {}
# maps alias -> (domain, key) where domain in {"carb","vitamin"}
for k, info in _CARBS.items():
    for a in info["aliases"]:
        _ALIAS_MAP[_lc(a)] = ("carb", k)
for k, info in _VITAMINS.items():
    for a in info["aliases"]:
        _ALIAS_MAP[_lc(a)] = ("vitamin", k)


def _find_entity(text: str) -> Optional[Tuple[str, str]]:
    t = _lc(text)
    # longest first to avoid partial capture
    aliases = sorted(_ALIAS_MAP.keys(), key=len, reverse=True)
    for a in aliases:
        if a and a in t:
            return _ALIAS_MAP[a]
    return None


def answer_biomolecules_question(cleaned_text: str, normalized: Dict[str, Any] | None = None) -> Optional[Dict[str, Any]]:
    """
    Deterministic Biomolecules v1:
      - Carbohydrates: type + reducing/non-reducing + standard tests
      - Vitamins: solubility + deficiency
      - Proteins/enzymes: theory
      - Nucleic acids: theory
    """
    q = _normalize_spaces(cleaned_text or "")
    low = _lc(q)

    # 1) Entity-specific answers first
    ent = _find_entity(q)
    if ent:
        domain, key = ent

        if domain == "carb":
            info = _CARBS[key]
            asks_reducing = _has_any(low, ["reducing", "non-reducing", "is it reducing", "is it non reducing"])
            asks_type = _has_any(low, ["monosaccharide", "disaccharide", "polysaccharide", "type of carbohydrate", "classify"])
            asks_test = _has_any(low, ["fehling", "tollens", "iodine", "test", "reaction"])
            asks_notes = _has_any(low, ["note", "property", "properties", "why", "reason"])

            if not (asks_reducing or asks_type or asks_test or asks_notes):
                return {
                    "topic": "BIOMOLECULES_V1",
                    "mode": "FACT_SUMMARY",
                    "entity": info["aliases"][0],
                    "type": info["type"],
                    "reducing": "REDUCING" if info["reducing"] else "NON-REDUCING",
                    "tests": info.get("tests", ""),
                    "notes": info.get("notes", ""),
                    "confidence": "DETERMINISTIC",
                }

            if asks_type:
                return {
                    "topic": "BIOMOLECULES_V1",
                    "mode": "CARB_TYPE",
                    "entity": info["aliases"][0],
                    "answer": info["type"],
                    "explanation": f"{info['aliases'][0]} is classified as: {info['type']}.",
                    "confidence": "DETERMINISTIC",
                }

            if asks_reducing:
                ans = "REDUCING" if info["reducing"] else "NON-REDUCING"
                return {
                    "topic": "BIOMOLECULES_V1",
                    "mode": "REDUCING_SUGAR",
                    "entity": info["aliases"][0],
                    "answer": ans,
                    "explanation": info.get("tests", ""),
                    "exam_tip": "Reducing sugars give positive Fehling's/Tollens' due to free (or effectively free) anomeric carbon.",
                    "confidence": "DETERMINISTIC",
                }

            if asks_test:
                return {
                    "topic": "BIOMOLECULES_V1",
                    "mode": "TESTS",
                    "entity": info["aliases"][0],
                    "answer": info.get("tests", ""),
                    "confidence": "DETERMINISTIC",
                }

            # asks_notes
            return {
                "topic": "BIOMOLECULES_V1",
                "mode": "NOTES",
                "entity": info["aliases"][0],
                "answer": info.get("notes", ""),
                "confidence": "DETERMINISTIC",
            }

        if domain == "vitamin":
            info = _VITAMINS[key]
            asks_solubility = _has_any(low, ["fat soluble", "water soluble", "soluble", "solubility"])
            asks_def = _has_any(low, ["deficiency", "disease", "causes", "leads to"])
            if not (asks_solubility or asks_def):
                return {
                    "topic": "BIOMOLECULES_V1",
                    "mode": "FACT_SUMMARY",
                    "entity": info["aliases"][0],
                    "solubility": info["solubility"],
                    "deficiency": info["deficiency"],
                    "confidence": "DETERMINISTIC",
                }

            if asks_solubility:
                return {
                    "topic": "BIOMOLECULES_V1",
                    "mode": "VITAMIN_SOLUBILITY",
                    "entity": info["aliases"][0],
                    "answer": info["solubility"],
                    "explanation": f"{info['aliases'][0]} is {info['solubility'].replace('_', ' ').lower()} (exam standard).",
                    "confidence": "DETERMINISTIC",
                }

            return {
                "topic": "BIOMOLECULES_V1",
                "mode": "VITAMIN_DEFICIENCY",
                "entity": info["aliases"][0],
                "answer": info["deficiency"],
                "confidence": "DETERMINISTIC",
            }

    # 2) Pure theory questions (no entity needed)
    if _has_any(low, ["peptide bond", "what is peptide bond", "define peptide bond"]):
        return {"topic": "BIOMOLECULES_V1", "mode": "THEORY", "answer": _PROTEINS["peptide_bond"]}

    if _has_any(low, ["primary structure", "secondary structure", "tertiary structure", "quaternary structure", "levels of protein"]):
        return {"topic": "BIOMOLECULES_V1", "mode": "THEORY", "answer": _PROTEINS["structure_levels"]}

    if _has_any(low, ["enzyme", "enzymes", "properties of enzymes", "what are enzymes"]):
        return {"topic": "BIOMOLECULES_V1", "mode": "THEORY", "answer": _PROTEINS["enzymes"]}

    if _has_any(low, ["dna vs rna", "difference between dna and rna", "dna and rna difference"]):
        return {"topic": "BIOMOLECULES_V1", "mode": "THEORY", "answer": _NUCLEIC_ACIDS["dna_vs_rna"]}

    if _has_any(low, ["nucleoside", "nucleotide", "difference between nucleoside and nucleotide"]):
        return {"topic": "BIOMOLECULES_V1", "mode": "THEORY", "answer": _NUCLEIC_ACIDS["nucleoside_vs_nucleotide"]}

    # 3) If user says biomolecules but no recognized entity/topic
    if _has_any(low, ["biomolecule", "biomolecules", "carbohydrate", "protein", "vitamin", "nucleic acid"]):
        return {
            "topic": "BIOMOLECULES_V1",
            "mode": "THEORY",
            "answer": "Biomolecules v1 supports carbohydrates (reducing/non-reducing, tests), vitamins (solubility/deficiency), proteins (peptide bond/structure), and nucleic acids (DNA vs RNA). Ask with a specific molecule/topic (e.g., sucrose reducing?, vitamin C deficiency?).",
        }

    return None
