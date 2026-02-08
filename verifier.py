import re
from typing import Tuple, List

NUM_RE = re.compile(r"[-+]?\d*\.?\d+(?:\s*[x×]\s*10\^[-+]?\d+)?")

def basic_verify(question: str, final_answer: str, steps: List[str]) -> Tuple[float, List[str], List[str]]:
    """
    Returns: (confidence_adjustment, flags, assumptions)
    confidence_adjustment is additive (can be negative).
    """
    flags = []
    assumptions = []
    adj = 0.0

    q = question.lower()

    # Ambiguity cues
    if any(w in q for w in ["why", "explain", "describe", "discuss"]):
        # fine; not ambiguous
        pass

    # Condition-dependent chemistry prompts (avoid confident wrong)
    if any(w in q for w in ["hbr", "hcl", "h2so4", "kmno4", "pcc", "tollens", "fehling", "naoh", "koh", "peroxide"]):
        if any(w in q for w in ["peroxide", "roh", "alcoholic", "aq", "acidic", "basic"]):
            pass
        else:
            # Often missing medium/conditions in exam questions
            flags.append("MISSING_CONDITIONS_POSSIBLE")
            assumptions.append("Assumed standard board/entrance conditions where not specified.")
            adj -= 0.08

    # Numerical sanity: if question has numbers but answer has none, lower confidence
    q_nums = NUM_RE.findall(question)
    a_nums = NUM_RE.findall(final_answer)
    if len(q_nums) >= 1 and len(a_nums) == 0 and ("calculate" in q or "find" in q or "value" in q):
        flags.append("NUMERICAL_ANSWER_MAY_BE_INCOMPLETE")
        adj -= 0.15

    # Steps should exist for step_by_step style
    if len(steps) == 0:
        flags.append("STEPS_MISSING")
        adj -= 0.05

    return adj, flags, assumptions
