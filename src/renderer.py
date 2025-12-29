def render_response(
    decision: str,
    understanding: str,
    concept: str,
    steps: str,
    final_answer: str,
    exam_tip: str,
    assumptions: list[str] | None = None
) -> dict:
    """
    Creates a strictly structured KnowEasy Engine response.
    """

    if assumptions is None:
        assumptions = []

    return {
        "decision": decision,
        "assumptions": assumptions,
        "sections": {
            "understanding": understanding,
            "concept": concept,
            "steps": steps,
            "final_answer": final_answer,
            "exam_tip": exam_tip
        }
    }
