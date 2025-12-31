import re

def guard_question(q: str) -> dict:
    """
    Returns FULL if safe to attempt.
    Returns PARTIAL if missing a key condition that often flips the answer.
    """
    q_l = q.lower()

    # If user wrote KOH but no medium mentioned, often ambiguous (substitution vs elimination)
    if "koh" in q_l and ("aqueous" not in q_l and "aq" not in q_l and "alcoholic" not in q_l and "ethanolic" not in q_l):
        return {
            "decision": "PARTIAL",
            "confidence": 0.45,
            "answer": "Need one condition: is KOH aqueous or alcoholic (ethanolic)?",
            "steps": [
                "Aqueous KOH usually favors substitution (alcohol formation).",
                "Alcoholic KOH usually favors elimination (alkene formation).",
            ],
            "exam_tip": "Write the product only after medium is known.",
            "flags": ["KOH_MEDIUM_MISSING"]
        }

    # Generic “product when X reacts with Y” but no reagents/conditions: still attempt via solver
    return {"decision": "FULL"}
