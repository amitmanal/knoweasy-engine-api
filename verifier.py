from typing import List, Tuple

def basic_verify(question: str, final_answer: str, steps: List[str]) -> Tuple[float, List[str], List[str]]:
    """Very light checks (Phase-1). Returns (confidence_adjustment, flags, assumptions)."""
    flags: List[str] = []
    assumptions: List[str] = []
    adj = 0.0

    q = (question or "").strip()
    a = (final_answer or "").strip()

    if not q:
        flags.append("EMPTY_QUESTION")
        adj -= 0.3

    if not a:
        flags.append("EMPTY_FINAL_ANSWER")
        adj -= 0.4

    if steps and not a:
        flags.append("STEPS_WITHOUT_FINAL")
        adj -= 0.2

    if len(a) < 3:
        flags.append("VERY_SHORT_ANSWER")
        adj -= 0.1

    return adj, flags, assumptions
