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
# Deterministic KB (exam-safe)
# -----------------------------
_DRUGS: Dict[str, Dict[str, Any]] = {
    "aspirin": {
        "aliases": ["aspirin", "acetylsalicylic acid"],
        "class": ["ANALGESIC", "ANTIPYRETIC", "ANTI-INFLAMMATORY (NSAID)"],
        "use": "Pain relief and fever reduction (exam standard).",
        "note": "Also used as anti-inflammatory (NSAID).",
    },
    "paracetamol": {
        "aliases": ["paracetamol", "acetaminophen"],
        "class": ["ANALGESIC", "ANTIPYRETIC"],
        "use": "Pain relief and fever reduction.",
        "note": "Commonly used antipyretic; not classified as antibiotic.",
    },
    "penicillin": {
        "aliases": ["penicillin"],
        "class": ["ANTIBIOTIC"],
        "use": "Antibiotic used against bacterial infections (exam standard).",
        "note": "Antibiotics act against bacteria; not against viruses.",
    },
    "streptomycin": {
        "aliases": ["streptomycin"],
        "class": ["ANTIBIOTIC"],
        "use": "Antibiotic (exam standard).",
        "note": "Used in bacterial infections; antibiotic category.",
    },
    "chloramphenicol": {
        "aliases": ["chloramphenicol"],
        "class": ["ANTIBIOTIC"],
        "use": "Antibiotic (exam standard).",
        "note": "Antibiotic category.",
    },
    "diazepam": {
        "aliases": ["diazepam"],
        "class": ["TRANQUILIZER"],
        "use": "Used as a tranquilizer (anti-anxiety/sedative in exam context).",
        "note": "Tranquilizers reduce anxiety and induce calmness.",
    },
    "milk_of_magnesia": {
        "aliases": ["milk of magnesia", "magnesium hydroxide", "mg(oh)2"],
        "class": ["ANTACID"],
        "use": "Neutralizes excess stomach acid (antacid).",
        "note": "Antacids are weak bases used to treat acidity.",
    },
    "sodium_bicarbonate": {
        "aliases": ["sodium bicarbonate", "nahco3", "baking soda"],
        "class": ["ANTACID"],
        "use": "Used as antacid (temporary relief).",
        "note": "Excess use can cause alkalosis (advanced); keep exam-safe.",
    },
    "iodine_tincture": {
        "aliases": ["tincture of iodine", "iodine"],
        "class": ["ANTISEPTIC"],
        "use": "Applied on wounds to prevent infection (antiseptic).",
        "note": "Antiseptics are applied to living tissues.",
    },
    "phenol": {
        "aliases": ["phenol", "carbolic acid"],
        "class": ["DISINFECTANT", "ANTISEPTIC (LOW CONC.)"],
        "use": "Used as disinfectant; at low concentration can act as antiseptic (exam standard).",
        "note": "Disinfectants are used on non-living surfaces.",
    },
    "sodium_benzoate": {
        "aliases": ["sodium benzoate"],
        "class": ["PRESERVATIVE"],
        "use": "Food preservative (prevents microbial growth).",
        "note": "Common preservative in acidic foods.",
    },
    "bht": {
        "aliases": ["bht", "butylated hydroxytoluene"],
        "class": ["ANTIOXIDANT"],
        "use": "Food antioxidant (prevents oxidation/rancidity).",
        "note": "Antioxidants prevent oxidative deterioration of food.",
    },
    "bha": {
        "aliases": ["bha", "butylated hydroxyanisole"],
        "class": ["ANTIOXIDANT"],
        "use": "Food antioxidant (prevents oxidation/rancidity).",
        "note": "Antioxidants prevent oxidation of food fats/oils.",
    },
    "saccharin": {
        "aliases": ["saccharin"],
        "class": ["ARTIFICIAL_SWEETENER"],
        "use": "Artificial sweetener (very sweet, used in diet foods).",
        "note": "Non-nutritive sweetener (exam standard).",
    },
    "aspartame": {
        "aliases": ["aspartame"],
        "class": ["ARTIFICIAL_SWEETENER"],
        "use": "Artificial sweetener (used in sugar-free products).",
        "note": "Not recommended for cooking at high temperature (often mentioned in textbooks).",
    },
}

_ALIAS_MAP: Dict[str, str] = {}
for k, info in _DRUGS.items():
    for a in info["aliases"]:
        _ALIAS_MAP[_lc(a)] = k


_THEORY: Dict[str, str] = {
    "antiseptic_vs_disinfectant": (
        "Antiseptics are applied to living tissues (wounds/skin) to prevent infection; "
        "disinfectants are used on non-living surfaces to kill microbes."
    ),
    "soap_vs_detergent": (
        "Soaps are sodium/potassium salts of long-chain fatty acids and form scum with Ca2+/Mg2+ in hard water. "
        "Detergents are synthetic cleansing agents that work better in hard water (do not form scum easily)."
    ),
    "analgesic_antipyretic": (
        "Analgesics relieve pain; antipyretics reduce fever. Some drugs (e.g., paracetamol/aspirin) show both actions."
    ),
    "antibiotic": (
        "Antibiotics are drugs used against bacterial infections; they do not act against viruses (exam standard)."
    ),
    "food_additives": (
        "Food additives include preservatives (prevent microbial spoilage), antioxidants (prevent oxidation/rancidity), and sweeteners."
    ),
}


def _find_drug_key(text: str) -> Optional[str]:
    t = _lc(text)
    aliases = sorted(_ALIAS_MAP.keys(), key=len, reverse=True)
    for a in aliases:
        if a and a in t:
            return _ALIAS_MAP[a]
    return None


def answer_everyday_life_question(cleaned_text: str, normalized: Dict[str, Any] | None = None) -> Optional[Dict[str, Any]]:
    """
    Chemistry in Everyday Life v1 (deterministic):
      - drug classification + use
      - antiseptic vs disinfectant
      - soap vs detergent
      - food additives: preservative/antioxidant/sweetener
    """
    q = _normalize_spaces(cleaned_text or "")
    low = _lc(q)

    # 1) Entity-specific first
    dk = _find_drug_key(q)
    if dk:
        info = _DRUGS[dk]

        # Intent
        asks_use = _has_any(low, ["use", "uses", "application", "used for", "purpose"])
        asks_class = _has_any(low, ["class", "category", "type", "belongs to"]) or _has_any(low, ["used as", "is used as"])
        asks_note = _has_any(low, ["note", "why", "reason", "explain"])

        classes = ", ".join(info["class"])

        if not (asks_class or asks_use or asks_note):
            return {
                "topic": "EVERYDAY_LIFE_V1",
                "mode": "FACT_SUMMARY",
                "entity": info["aliases"][0],
                "classification": classes,
                "use": info.get("use", ""),
                "note": info.get("note", ""),
                "confidence": "DETERMINISTIC",
            }

        # IMPORTANT: classification wins over use for "used as" pattern (e.g., sodium benzoate used as what?)
        if asks_class:
            return {
                "topic": "EVERYDAY_LIFE_V1",
                "mode": "CLASSIFICATION",
                "entity": info["aliases"][0],
                "answer": classes,
                "explanation": info.get("note", ""),
                "confidence": "DETERMINISTIC",
            }

        if asks_use:
            return {
                "topic": "EVERYDAY_LIFE_V1",
                "mode": "USES",
                "entity": info["aliases"][0],
                "answer": info.get("use", ""),
                "confidence": "DETERMINISTIC",
            }

        return {
            "topic": "EVERYDAY_LIFE_V1",
            "mode": "NOTES",
            "entity": info["aliases"][0],
            "answer": info.get("note", ""),
            "confidence": "DETERMINISTIC",
        }

    # 2) Theory triggers
    if _has_any(low, ["antiseptic", "disinfectant", "difference between antiseptic", "difference between disinfectant", "differentiate between antiseptic", "differentiate between disinfectant"]):
        return {"topic": "EVERYDAY_LIFE_V1", "mode": "THEORY", "answer": _THEORY["antiseptic_vs_disinfectant"]}

    if _has_any(low, ["soap", "detergent", "difference between soap", "difference between detergent", "soap vs detergent"]):
        return {"topic": "EVERYDAY_LIFE_V1", "mode": "THEORY", "answer": _THEORY["soap_vs_detergent"]}

    if _has_any(low, ["analgesic", "antipyretic", "difference between analgesic", "difference between antipyretic"]):
        return {"topic": "EVERYDAY_LIFE_V1", "mode": "THEORY", "answer": _THEORY["analgesic_antipyretic"]}

    if _has_any(low, ["antibiotic", "antibiotics", "what are antibiotics", "define antibiotic"]):
        return {"topic": "EVERYDAY_LIFE_V1", "mode": "THEORY", "answer": _THEORY["antibiotic"]}

    if _has_any(low, ["food additive", "preservative", "antioxidant", "sweetener", "food additives"]):
        return {"topic": "EVERYDAY_LIFE_V1", "mode": "THEORY", "answer": _THEORY["food_additives"]}

    # 3) Generic help
    if _has_any(low, ["chemistry in everyday life", "everyday life"]):
        return {
            "topic": "EVERYDAY_LIFE_V1",
            "mode": "THEORY",
            "answer": "Everyday Life v1 supports drugs (classification/uses), antiseptic vs disinfectant, soap vs detergent, and food additives (preservatives/antioxidants/sweeteners). Ask with a specific item (e.g., aspirin class?, sodium benzoate used as what?).",
        }

    return None
