import re

_SUBSCRIPT_MAP = str.maketrans({
    "₀":"0","₁":"1","₂":"2","₃":"3","₄":"4",
    "₅":"5","₆":"6","₇":"7","₈":"8","₉":"9",
})

_SUPERSCRIPT_MAP = str.maketrans({
    "⁰":"0","¹":"1","²":"2","³":"3","⁴":"4",
    "⁵":"5","⁶":"6","⁷":"7","⁸":"8","⁹":"9",
    "⁺":"+","⁻":"-",
})

def normalize_question(q: str) -> str:
    if not q:
        return ""

    # Normalize unicode subscripts/superscripts
    q = q.translate(_SUBSCRIPT_MAP).translate(_SUPERSCRIPT_MAP)

    # Normalize common arrow variants
    q = q.replace("→", "->").replace("⇒", "->").replace("⟶", "->")

    # Normalize special dashes/quotes
    q = q.replace("–", "-").replace("—", "-").replace("“", '"').replace("”", '"').replace("’", "'")

    # Collapse spaces
    q = re.sub(r"\s+", " ", q).strip()

    return q
