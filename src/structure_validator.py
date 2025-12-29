REQUIRED_SECTIONS = [
    "understanding",
    "concept",
    "steps",
    "final_answer",
    "exam_tip"
]

def validate_structure(response: dict) -> tuple[bool, str]:
    """
    Validates that the response follows KnowEasy Engine structure rules.
    Returns (is_valid, error_message)
    """

    if "sections" not in response:
        return False, "Missing 'sections' object"

    sections = response["sections"]

    for key in REQUIRED_SECTIONS:
        if key not in sections:
            return False, f"Missing section: {key}"

        if not isinstance(sections[key], str):
            return False, f"Section '{key}' must be a string"

        if sections[key].strip() == "":
            return False, f"Section '{key}' cannot be empty"

    return True, "OK"
