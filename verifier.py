from typing import List, Tuple

def basic_verify(question: str, final_answer: str, steps: List[str]) -> Tuple[float, List[str], List[str]]:
    """
    Returns:
      (confidence_adjustment, flags, assumptions)
    Very light, safe checks only (Phase-1).
    """
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

    # If steps exist but final answer empty → suspicious
    if steps and not a:
        flags.append("STEPS_WITHOUT_FINAL")
        adj -= 0.2

    # If question looks like a multiple-choice but answer doesn't pick one
    if any(opt in q for opt in ["(A)", "(B)", "(C)", "(D)", "A)", "B)", "C)", "D)"]) and not any(x in a for x in ["A", "B", "C", "D"]):
        flags.append("MCQ_NO_OPTION_SELECTED")
        assumptions.append("Question appears to be MCQ; answer may need selecting an option (A/B/C/D).")
        adj -= 0.1

    return adj, flags, assumptions
