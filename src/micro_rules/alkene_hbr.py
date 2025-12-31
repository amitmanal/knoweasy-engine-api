def solve_alkene_hbr(question: str):
    q = question.lower()

    if "hbr" not in q:
        return None

    if "peroxide" in q or "roor" in q:
        return {
            "answer": "Anti-Markovnikov addition: bromine attaches to the less substituted carbon.",
            "confidence": 0.98,
            "flags": ["ANTI_MARKOVNIKOV", "HBR_PEROXIDE"]
        }

    if "no peroxide" in q or "absence of peroxide" in q:
        return {
            "answer": "Markovnikov addition: bromine attaches to the more substituted carbon.",
            "confidence": 0.98,
            "flags": ["MARKOVNIKOV", "HBR_NO_PEROXIDE"]
        }

    return None
