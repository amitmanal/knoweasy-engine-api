from __future__ import annotations

from typing import Any, Dict, Optional, List


def _lc(s: str) -> str:
    return (s or "").strip().lower()


def _has_any(text: str, words: List[str]) -> bool:
    t = _lc(text)
    return any(w in t for w in words)


def _normalize_spaces(s: str) -> str:
    return " ".join((s or "").split())


# -----------------------------
# Deterministic knowledge base
# -----------------------------
_POLYMERS_DB: Dict[str, Dict[str, Any]] = {
    "polythene": {
        "aliases": ["polyethene", "polyethylene", "polythene", "pe"],
        "monomers": ["ethene (ethylene)"],
        "type": "ADDITION",
        "class": ["THERMOPLASTIC"],
        "uses": "Packaging, carry bags, bottles, containers (general uses).",
        "exam_tip": "Polythene is an addition polymer of ethene.",
    },
    "pvc": {
        "aliases": ["pvc", "polyvinyl chloride", "poly(vinyl chloride)"],
        "monomers": ["vinyl chloride (chloroethene)"],
        "type": "ADDITION",
        "class": ["THERMOPLASTIC"],
        "uses": "Pipes, insulation of wires, raincoats (general uses).",
        "exam_tip": "PVC is an addition polymer; monomer is vinyl chloride.",
    },
    "ptfe": {
        "aliases": ["ptfe", "teflon", "polytetrafluoroethylene"],
        "monomers": ["tetrafluoroethene (TFE)"],
        "type": "ADDITION",
        "class": ["THERMOPLASTIC"],
        "uses": "Non-stick coatings, chemical-resistant linings.",
        "exam_tip": "Teflon = PTFE, monomer is tetrafluoroethene.",
    },
    "bakelite": {
        "aliases": ["bakelite", "phenol-formaldehyde resin", "phenol formaldehyde"],
        "monomers": ["phenol", "formaldehyde (methanal)"],
        "type": "CONDENSATION",
        "class": ["THERMOSETTING"],
        "uses": "Electrical switches, handles, laminates (general uses).",
        "exam_tip": "Bakelite is a thermosetting condensation polymer.",
    },
    "melamine_formaldehyde": {
        "aliases": ["melamine formaldehyde", "melamine-formaldehyde resin"],
        "monomers": ["melamine", "formaldehyde (methanal)"],
        "type": "CONDENSATION",
        "class": ["THERMOSETTING"],
        "uses": "Unbreakable crockery, laminates (general uses).",
        "exam_tip": "Melamine-formaldehyde is thermosetting.",
    },
    "nylon_6_6": {
        "aliases": ["nylon 6,6", "nylon-6,6", "nylon 66", "nylon66"],
        "monomers": ["hexamethylenediamine", "adipic acid (hexanedioic acid)"],
        "type": "CONDENSATION",
        "class": ["FIBRE"],
        "uses": "Fibres for textiles, ropes, tyre cords (general uses).",
        "exam_tip": "Nylon-6,6 is formed from hexamethylenediamine + adipic acid (condensation).",
    },
    "nylon_6": {
        "aliases": ["nylon 6", "nylon-6"],
        "monomers": ["caprolactam (via ring opening)"],
        "type": "ADDITION",  # ring-opening; exam-friendly bucket
        "class": ["FIBRE"],
        "uses": "Fibres, engineering plastics.",
        "exam_tip": "Nylon-6 is produced from caprolactam (ring opening).",
    },
    "terylene": {
        "aliases": ["terylene", "dacron", "pet", "polyethylene terephthalate"],
        "monomers": ["ethylene glycol", "terephthalic acid (benzene-1,4-dicarboxylic acid)"],
        "type": "CONDENSATION",
        "class": ["FIBRE", "THERMOPLASTIC"],
        "uses": "Polyester fibres, bottles (PET).",
        "exam_tip": "Terylene/Dacron/PET is a condensation polymer of ethylene glycol + terephthalic acid.",
    },
    "buna_s": {
        "aliases": ["buna-s", "sbr", "styrene butadiene rubber"],
        "monomers": ["1,3-butadiene", "styrene"],
        "type": "ADDITION",
        "class": ["ELASTOMER"],
        "uses": "Tyres, rubber goods.",
        "exam_tip": "Buna-S = butadiene + styrene (addition copolymer).",
    },
    "buna_n": {
        "aliases": ["buna-n", "nbr", "nitrile rubber"],
        "monomers": ["1,3-butadiene", "acrylonitrile"],
        "type": "ADDITION",
        "class": ["ELASTOMER"],
        "uses": "Oil-resistant rubber goods.",
        "exam_tip": "Buna-N = butadiene + acrylonitrile.",
    },
    "neoprene": {
        "aliases": ["neoprene", "polychloroprene", "chloroprene rubber"],
        "monomers": ["chloroprene (2-chloro-1,3-butadiene)"],
        "type": "ADDITION",
        "class": ["ELASTOMER"],
        "uses": "Oil/chemical resistant rubber products.",
        "exam_tip": "Neoprene is the polymer of chloroprene.",
    },
    "gutta_percha": {
        "aliases": ["gutta-percha", "gutta percha"],
        "monomers": ["isoprene (exam-standard reference)"],
        "type": "ADDITION",
        "class": ["NATURAL"],
        "uses": "Natural polymer (historical uses).",
        "exam_tip": "Gutta-percha is a natural polymer of isoprene.",
    },
    "natural_rubber": {
        "aliases": ["natural rubber", "rubber", "polyisoprene"],
        "monomers": ["isoprene (2-methyl-1,3-butadiene)"],
        "type": "ADDITION",
        "class": ["NATURAL", "ELASTOMER"],
        "uses": "Rubber products; vulcanization improves properties.",
        "exam_tip": "Natural rubber is cis-1,4-polyisoprene (exam standard).",
    },
}

_ALIAS_TO_KEY: Dict[str, str] = {}
for key, info in _POLYMERS_DB.items():
    for a in info["aliases"]:
        _ALIAS_TO_KEY[_lc(a)] = key


_THEORY: Dict[str, str] = {
    "addition_polymerization": (
        "Addition polymerization: monomers (usually alkenes) add to form a polymer without elimination of small molecules."
    ),
    "condensation_polymerization": (
        "Condensation polymerization: bifunctional monomers combine with elimination of small molecules (e.g., H2O, HCl) to form a polymer."
    ),
    "thermoplastic_vs_thermosetting": (
        "Thermoplastics soften on heating and can be remoulded; thermosetting polymers are highly cross-linked and do not soften on heating."
    ),
    "copolymer": (
        "Copolymers are formed from two (or more) different monomers (e.g., Buna-S from butadiene + styrene)."
    ),
}


def _find_polymer_key_from_text(text: str) -> Optional[str]:
    t = _lc(text)
    aliases = sorted(_ALIAS_TO_KEY.keys(), key=len, reverse=True)
    for a in aliases:
        if a and a in t:
            return _ALIAS_TO_KEY[a]
    return None


def _format_monomers(monomers: List[str]) -> str:
    if not monomers:
        return "UNKNOWN"
    if len(monomers) == 1:
        return monomers[0]
    return " + ".join(monomers)


def answer_polymers_question(cleaned_text: str, normalized: Dict[str, Any] | None = None) -> Optional[Dict[str, Any]]:
    """
    Deterministic Polymers v1.

    Bugfix policy:
      - If a specific polymer is detected, answer polymer-specific intent FIRST.
      - Only if no polymer is detected, then allow general THEORY shortcuts.
    """
    q = _normalize_spaces(cleaned_text or "")
    low = _lc(q)

    # 1) Detect polymer first (prevents THEORY keyword hijack like thermoplastic/thermosetting)
    key = _find_polymer_key_from_text(q)
    if key:
        info = _POLYMERS_DB[key]

        asks_monomer = _has_any(low, ["monomer", "monomers", "made from", "formed from", "prepared from", "starting material"])
        asks_type = _has_any(low, ["addition or condensation", "type of polymerization", "polymerization type", "addition polymer", "condensation polymer"])
        asks_class = _has_any(low, ["thermoplastic", "thermosetting", "elastomer", "fibre", "fiber", "natural or synthetic", "natural", "synthetic"])
        asks_use = _has_any(low, ["use", "uses", "application", "applications"])

        monomers_txt = _format_monomers(info["monomers"])
        poly_type = info["type"]
        poly_class = ", ".join(info["class"]) if isinstance(info.get("class"), list) else str(info.get("class", ""))
        tip = info.get("exam_tip", "")

        if not (asks_monomer or asks_type or asks_class or asks_use):
            return {
                "topic": "POLYMERS_V1",
                "mode": "FACT_SUMMARY",
                "polymer": info["aliases"][0],
                "monomers": monomers_txt,
                "polymerization": poly_type,
                "classification": poly_class,
                "uses": info.get("uses", ""),
                "exam_tip": tip,
                "confidence": "DETERMINISTIC",
            }

        if asks_monomer:
            return {
                "topic": "POLYMERS_V1",
                "mode": "MONOMER",
                "polymer": info["aliases"][0],
                "answer": monomers_txt,
                "explanation": f"{info['aliases'][0]} is formed from: {monomers_txt}.",
                "exam_tip": tip,
                "confidence": "DETERMINISTIC",
            }

        if asks_type:
            return {
                "topic": "POLYMERS_V1",
                "mode": "POLYMERIZATION_TYPE",
                "polymer": info["aliases"][0],
                "answer": poly_type,
                "explanation": f"{info['aliases'][0]} is classified as a {poly_type.lower()} polymerization product (exam standard).",
                "exam_tip": tip,
                "confidence": "DETERMINISTIC",
            }

        if asks_class:
            return {
                "topic": "POLYMERS_V1",
                "mode": "CLASSIFICATION",
                "polymer": info["aliases"][0],
                "answer": poly_class,
                "explanation": f"Classification tags for {info['aliases'][0]}: {poly_class}.",
                "exam_tip": tip,
                "confidence": "DETERMINISTIC",
            }

        if asks_use:
            return {
                "topic": "POLYMERS_V1",
                "mode": "USES",
                "polymer": info["aliases"][0],
                "answer": info.get("uses", ""),
                "exam_tip": tip,
                "confidence": "DETERMINISTIC",
            }

        return {
            "topic": "POLYMERS_V1",
            "mode": "FACT_SUMMARY",
            "polymer": info["aliases"][0],
            "monomers": monomers_txt,
            "polymerization": poly_type,
            "classification": poly_class,
            "uses": info.get("uses", ""),
            "exam_tip": tip,
            "confidence": "DETERMINISTIC",
        }

    # 2) No polymer detected → allow THEORY triggers
    if _has_any(low, ["define addition polymerization", "what is addition polymerization", "addition polymerisation"]):
        return {"topic": "POLYMERS_V1", "mode": "THEORY", "answer": _THEORY["addition_polymerization"]}

    if _has_any(low, ["define condensation polymerization", "what is condensation polymerization", "condensation polymerisation"]):
        return {"topic": "POLYMERS_V1", "mode": "THEORY", "answer": _THEORY["condensation_polymerization"]}

    if _has_any(low, ["thermoplastic", "thermosetting", "difference between thermoplastic", "difference between thermosetting"]):
        return {"topic": "POLYMERS_V1", "mode": "THEORY", "answer": _THEORY["thermoplastic_vs_thermosetting"]}

    if _has_any(low, ["copolymer", "copolymerization", "copolymerisation"]):
        return {"topic": "POLYMERS_V1", "mode": "THEORY", "answer": _THEORY["copolymer"]}

    if _has_any(low, ["polymer", "monomer", "polymers"]):
        return {
            "topic": "POLYMERS_V1",
            "mode": "THEORY",
            "answer": "Polymers v1 supports common NCERT/exam polymers. Please mention the polymer name (e.g., PVC, Teflon, Nylon-6,6, Bakelite).",
        }

    return None
