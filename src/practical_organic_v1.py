from __future__ import annotations

from typing import Any, Dict, List, Optional


def _lc(s: str) -> str:
    return (s or "").strip().lower()


def _normalize_spaces(s: str) -> str:
    return " ".join((s or "").split())


def _has_any(text: str, words: List[str]) -> bool:
    t = _lc(text)
    return any(w in t for w in words)


_THEORY: Dict[str, str] = {
    "lassaigne_n": "Lassaigne’s test for nitrogen: Fuse compound with Na → extract (Lassaigne’s extract) → add FeSO4, boil, acidify → Prussian blue color indicates nitrogen.",
    "lassaigne_s": "Lassaigne’s test for sulphur: Sodium fusion converts S → Na2S; add sodium nitroprusside → violet/purple color indicates sulphur (exam standard).",
    "lassaigne_x": "Lassaigne’s test for halogens: Sodium fusion converts X → NaX; acidify with HNO3, then add AgNO3 → AgCl (white), AgBr (pale yellow), AgI (yellow) precipitate.",
    "tollens": "Tollens’ test: Aldehydes reduce Tollens’ reagent to give silver mirror; ketones generally do not.",
    "fehling": "Fehling’s test: Aliphatic aldehydes reduce Fehling’s solution to red Cu2O precipitate; ketones generally do not.",
    "iodoform": "Iodoform test (I2/NaOH): Yellow precipitate of CHI3 indicates presence of CH3CO– (methyl ketone) or CH3CH(OH)– group (e.g., ethanol/acetaldehyde give positive).",
    "nabhco3": "Carboxylic acids react with NaHCO3 giving brisk effervescence of CO2 (acid test).",
    "fecl3_phenol": "Phenols give colored complex with neutral FeCl3 (often violet/blue/green depending on phenol).",
    "bromine_water_phenol": "Phenol decolorizes bromine water giving white precipitate of 2,4,6-tribromophenol (exam standard).",
    "lucas": "Lucas test (conc. HCl + ZnCl2): 3° alcohol → immediate turbidity; 2° → turbidity in few minutes; 1° → no turbidity at room temperature.",
    "baeyer": "Baeyer test (cold dilute alkaline KMnO4): Unsaturation (C=C/C≡C) decolorizes purple KMnO4 with formation of brown MnO2 (exam standard).",
}


def answer_practical_organic_question(cleaned_text: str, normalized: Dict[str, Any] | None = None) -> Optional[Dict[str, Any]]:
    """
    Practical Organic Chemistry v1 (deterministic):
      - Lassaigne’s test (N, S, halogens)
      - Tollens / Fehling (aldehyde vs ketone)
      - Iodoform test
      - NaHCO3 test for carboxylic acids
      - FeCl3 / Bromine water for phenols
      - Lucas test (alcohol classification)
      - Baeyer test (unsaturation)
    """
    q = _normalize_spaces(cleaned_text or "")
    low = _lc(q)

    # Lassaigne’s tests (IMPORTANT: halogens check first; avoid false trigger from "'s test")
    if _has_any(low, ["lassaigne", "lassaignes", "sodium fusion"]):
        # Halogens first (most common phrasing in questions)
        if _has_any(low, ["halogen", "halogens", "test for halogen", "x test", "chloride", "bromide", "iodide", "agcl", "agbr", "agi"]):
            return {"topic": "PRACTICAL_ORGANIC_V1", "mode": "TEST", "answer": _THEORY["lassaigne_x"], "confidence": "DETERMINISTIC"}

        # Nitrogen
        if _has_any(low, ["nitrogen", "test for nitrogen", "prussian blue"]):
            return {"topic": "PRACTICAL_ORGANIC_V1", "mode": "TEST", "answer": _THEORY["lassaigne_n"], "confidence": "DETERMINISTIC"}

        # Sulphur (strong triggers only)
        if _has_any(low, ["sulphur", "sulfur", "test for sulphur", "test for sulfur", "nitroprusside"]):
            return {"topic": "PRACTICAL_ORGANIC_V1", "mode": "TEST", "answer": _THEORY["lassaigne_s"], "confidence": "DETERMINISTIC"}

        return {
            "topic": "PRACTICAL_ORGANIC_V1",
            "mode": "THEORY",
            "answer": "Lassaigne’s (sodium fusion) test is used to detect extra elements like N, S, and halogens in organic compounds.",
            "confidence": "DETERMINISTIC",
        }

    # Tollens / Fehling
    if _has_any(low, ["tollens", "silver mirror"]):
        return {"topic": "PRACTICAL_ORGANIC_V1", "mode": "TEST", "answer": _THEORY["tollens"], "confidence": "DETERMINISTIC"}

    if _has_any(low, ["fehling", "cu2o", "red precipitate"]):
        return {"topic": "PRACTICAL_ORGANIC_V1", "mode": "TEST", "answer": _THEORY["fehling"], "confidence": "DETERMINISTIC"}

    # Iodoform
    if _has_any(low, ["iodoform test", "iodoform", "chi3", "yellow precipitate"]):
        return {"topic": "PRACTICAL_ORGANIC_V1", "mode": "TEST", "answer": _THEORY["iodoform"], "confidence": "DETERMINISTIC"}

    # NaHCO3 test
    if _has_any(low, ["nahco3", "sodium bicarbonate"]) or (_has_any(low, ["effervescence", "co2"]) and _has_any(low, ["acid", "carboxylic"])):
        return {"topic": "PRACTICAL_ORGANIC_V1", "mode": "TEST", "answer": _THEORY["nabhco3"], "confidence": "DETERMINISTIC"}

    # Phenol tests
    if _has_any(low, ["fecl3", "ferric chloride"]) and _has_any(low, ["phenol", "phenolic"]):
        return {"topic": "PRACTICAL_ORGANIC_V1", "mode": "TEST", "answer": _THEORY["fecl3_phenol"], "confidence": "DETERMINISTIC"}

    if _has_any(low, ["bromine water"]) and _has_any(low, ["phenol", "phenolic"]):
        return {"topic": "PRACTICAL_ORGANIC_V1", "mode": "TEST", "answer": _THEORY["bromine_water_phenol"], "confidence": "DETERMINISTIC"}

    # Lucas test
    if _has_any(low, ["lucas test", "zncl2", "conc hcl", "turbidity"]):
        return {"topic": "PRACTICAL_ORGANIC_V1", "mode": "TEST", "answer": _THEORY["lucas"], "confidence": "DETERMINISTIC"}

    # Baeyer test
    if _has_any(low, ["baeyer", "kmno4", "alkaline kmno4", "dilute kmno4", "brown mno2"]):
        return {"topic": "PRACTICAL_ORGANIC_V1", "mode": "TEST", "answer": _THEORY["baeyer"], "confidence": "DETERMINISTIC"}

    # Generic trigger
    if _has_any(low, ["practical organic", "qualitative analysis", "identify functional group", "organic test", "test for"]):
        return {
            "topic": "PRACTICAL_ORGANIC_V1",
            "mode": "THEORY",
            "answer": "Practical Organic v1 supports: Lassaigne’s (N/S/halogens), Tollens/Fehling (aldehydes), iodoform (methyl ketone/ethanol), NaHCO3 (carboxylic acid), FeCl3/bromine water (phenol), Lucas (alcohol class), Baeyer (unsaturation). Ask with a specific test name.",
            "confidence": "DETERMINISTIC",
        }

    return None
