# src/question_type_genome_v1.py

import re

REACTION_KEYWORDS = [
    "reacts with", "gives", "product", "predict", "on treatment with",
    "+", "→", "-->", "yields", "forms"
]

ORDER_KEYWORDS = [
    "order of", "arrange", "increasing", "decreasing", "rank"
]

IUPAC_KEYWORDS = [
    "iupac", "name the compound", "give name", "nomenclature"
]

TEST_KEYWORDS = [
    "test", "iodoform", "carbylamine", "tollen", "fehling"
]

MECHANISM_KEYWORDS = [
    "mechanism", "sn1", "sn2", "e1", "e2", "explain how"
]

CONCEPT_KEYWORDS = [
    "isomerism", "explain", "why", "define", "theory"
]


def detect_question_type(question: str) -> str:
    q = question.lower()

    for k in ORDER_KEYWORDS:
        if k in q:
            return "ORDER_RANKING"

    for k in IUPAC_KEYWORDS:
        if k in q:
            return "IUPAC"

    for k in TEST_KEYWORDS:
        if k in q:
            return "TEST_ID"

    for k in MECHANISM_KEYWORDS:
        if k in q:
            return "MECHANISM"

    for k in REACTION_KEYWORDS:
        if k in q:
            return "REACTION"

    for k in CONCEPT_KEYWORDS:
        if k in q:
            return "CONCEPT"

    return "UNKNOWN"
