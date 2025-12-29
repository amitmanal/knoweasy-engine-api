from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional


@dataclass(frozen=True)
class StereoResult:
    """
    Deterministic stereochemistry answer payload.

    confidence:
      - "DETERMINISTIC" => computed from explicit structured input
      - "PARTIAL"       => derived from a known DB pair or partial data
    """
    mode: str  # THEORY / RS_ASSIGNMENT / EZ_ASSIGNMENT / CHIRALITY / OPTICAL_ACTIVITY
    answer: str
    explanation: str = ""
    concept: str = "STEREOCHEMISTRY (v1)"
    steps: str = ""
    exam_tip: str = ""
    common_mistake: str = ""
    confidence: str = "DETERMINISTIC"


def _lc(s: str) -> str:
    return (s or "").strip().lower()


def _has_any(text: str, words: list[str]) -> bool:
    t = _lc(text)
    return any(w in t for w in words)


def _get_vision_json(normalized: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """
    Supports both:
      normalized["vision_json"] and normalized["vision"]
    """
    if not isinstance(normalized, dict):
        return None
    v = normalized.get("vision_json")
    if isinstance(v, dict):
        return v
    v = normalized.get("vision")
    if isinstance(v, dict):
        return v
    return None


def _extract_stereo_payload(v: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """
    Accepts flexible shapes, but returns a single stereochemistry dict.

    Supported patterns:
      1) {"task":"stereochemistry", "subtask":"RS", ...}
      2) {"question_type":"stereochemistry", "stereo": {...}}
      3) {"stereo": {"subtask":"EZ", ...}}
    """
    if not isinstance(v, dict):
        return None

    # direct
    if _lc(str(v.get("task", ""))) in ("stereochemistry", "stereo"):
        return v
    if _lc(str(v.get("question_type", ""))) in ("stereochemistry", "stereo"):
        payload = v.get("stereo")
        if isinstance(payload, dict):
            return payload

    payload = v.get("stereo")
    if isinstance(payload, dict):
        return payload

    return None


def _rs_from_cip(
    *,
    sequence_direction: str,
    lowest_priority_is_away: bool,
) -> str:
    """
    With lowest priority group away:
      clockwise => R
      counterclockwise => S
    If lowest priority is NOT away, invert result.

    sequence_direction expects "clockwise" or "counterclockwise".
    """
    sd = _lc(sequence_direction)
    if sd not in ("clockwise", "counterclockwise"):
        raise ValueError("sequence_direction must be 'clockwise' or 'counterclockwise'")

    base = "R" if sd == "clockwise" else "S"
    if lowest_priority_is_away:
        return base
    # invert
    return "S" if base == "R" else "R"


def _ez_from_side(same_side: bool) -> str:
    return "Z" if same_side else "E"


def _chirality_from_flags(*, chiral_centers: int, plane_of_symmetry: bool) -> Dict[str, str]:
    """
    Deterministic:
      - 0 chiral centers => achiral
      - plane of symmetry present AND chiral centers > 0 => meso (achiral overall)
      - otherwise => chiral
    """
    if chiral_centers <= 0:
        return {"chirality": "ACHIRAL", "note": "No chiral center indicated."}
    if plane_of_symmetry:
        return {"chirality": "MESO", "note": "Plane of symmetry indicated → meso (achiral overall)."}
    return {"chirality": "CHIRAL", "note": "Chiral center(s) present and no symmetry indicated."}


_THEORY_SNIPPETS: Dict[str, str] = {
    "chirality": (
        "Chirality: a molecule is chiral if it is not superimposable on its mirror image. "
        "A common cause is a stereogenic (chiral) center: a tetrahedral carbon attached to four different groups."
    ),
    "rs": (
        "R/S configuration (CIP): assign priorities 1–4 by atomic number; orient lowest priority (4) away; "
        "trace 1→2→3: clockwise = R, counterclockwise = S (invert if group 4 is toward you)."
    ),
    "ez": (
        "E/Z configuration: assign CIP priority on each alkene carbon; if the two highest-priority groups are on the same side → Z; "
        "opposite sides → E. (cis/trans is only valid for simple cases with identical groups.)"
    ),
    "meso": (
        "Meso compound: contains stereocenters but is achiral overall due to an internal plane of symmetry; "
        "therefore it is optically inactive (internal compensation)."
    ),
    "enantiomer_diastereo": (
        "Enantiomers are non-superimposable mirror images (opposite configuration at all stereocenters). "
        "Diastereomers are stereoisomers that are not mirror images (differ at some but not all stereocenters)."
    ),
}


def answer_stereochemistry_question(cleaned_text: str, normalized: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """
    Returns a dict:
      {"topic":"STEREOCHEMISTRY_V1", "mode":..., ...}
    or None if not stereochemistry.

    Deterministic policy:
      - R/S and E/Z require explicit structured input from vision JSON.
      - Text-only support is limited to theory + a small DB of known pairs.

    IMPORTANT (bugfix):
      Structured vision data must be processed BEFORE theory shortcuts,
      otherwise prompts like "Assign R/S" incorrectly return THEORY.
    """
    text = (cleaned_text or "").strip()
    low = _lc(text)

    # ---- 1) Structured vision JSON path FIRST (deterministic computation) ----
    v = _get_vision_json(normalized)
    payload = _extract_stereo_payload(v) if v else None
    if payload:
        subtask = _lc(str(payload.get("subtask", payload.get("type", ""))))

        if subtask in ("rs", "r/s", "rs_assignment"):
            sd = payload.get("sequence_direction")
            away = payload.get("lowest_priority_is_away")
            if not isinstance(sd, str) or not isinstance(away, bool):
                return {
                    "topic": "STEREOCHEMISTRY_V1",
                    "mode": "RS_ASSIGNMENT",
                    "concept": "R/S CONFIGURATION (CIP)",
                    "steps": "Need: sequence_direction ('clockwise'/'counterclockwise') and lowest_priority_is_away (true/false).",
                    "answer": "INSUFFICIENT DATA",
                    "explanation": "Structured stereochemistry input is incomplete.",
                    "exam_tip": "For R/S, always place group-4 away; if group-4 is toward you, invert the result.",
                    "common_mistake": "Trying to assign R/S from text without wedge/dash or priority/orientation data.",
                    "confidence": "PARTIAL",
                }

            rs = _rs_from_cip(sequence_direction=sd, lowest_priority_is_away=away)
            pr = payload.get("cip_priorities")
            pr_txt = ""
            if isinstance(pr, list) and len(pr) >= 4:
                pr_txt = f"CIP priorities: 1>{pr[0]}, 2>{pr[1]}, 3>{pr[2]}, 4>{pr[3]}."
            expl = f"With lowest priority {'away' if away else 'toward'}, 1→2→3 is {sd} ⇒ {rs}. {pr_txt}".strip()

            return {
                "topic": "STEREOCHEMISTRY_V1",
                "mode": "RS_ASSIGNMENT",
                "concept": "R/S CONFIGURATION (CIP)",
                "steps": "1) Assign CIP priorities 1–4.\n2) Ensure priority-4 is away.\n3) Trace 1→2→3: clockwise=R, counterclockwise=S.\n4) If priority-4 is toward, invert.",
                "answer": rs,
                "explanation": expl,
                "exam_tip": "Clockwise with group-4 away = R; counterclockwise = S; invert if group-4 is toward you.",
                "common_mistake": "Forgetting to invert when the lowest priority is not pointing away.",
                "confidence": "DETERMINISTIC",
            }

        if subtask in ("ez", "e/z", "ez_assignment"):
            same_side = payload.get("same_side")
            if not isinstance(same_side, bool):
                return {
                    "topic": "STEREOCHEMISTRY_V1",
                    "mode": "EZ_ASSIGNMENT",
                    "concept": "E/Z CONFIGURATION (CIP)",
                    "steps": "Need: same_side (true/false) for the two highest priority groups on each alkene carbon.",
                    "answer": "INSUFFICIENT DATA",
                    "explanation": "Structured stereochemistry input is incomplete.",
                    "exam_tip": "Assign CIP on each alkene carbon, then compare the two highest-priority groups: same side → Z, opposite → E.",
                    "common_mistake": "Using cis/trans when groups are not identical; skipping CIP priority assignment.",
                    "confidence": "PARTIAL",
                }

            ez = _ez_from_side(same_side)
            return {
                "topic": "STEREOCHEMISTRY_V1",
                "mode": "EZ_ASSIGNMENT",
                "concept": "E/Z CONFIGURATION (CIP)",
                "steps": "1) Assign CIP priority on each alkene carbon.\n2) Compare the two highest priorities: same side → Z, opposite → E.",
                "answer": ez,
                "explanation": "Highest priority groups are on the same side." if same_side else "Highest priority groups are on opposite sides.",
                "exam_tip": "Z = zusammen (together); E = entgegen (opposite).",
                "common_mistake": "Calling cis/trans for substituted alkenes without checking identical groups.",
                "confidence": "DETERMINISTIC",
            }

        if subtask in ("chirality", "chiral", "achiral", "meso"):
            cc = payload.get("chiral_centers", 0)
            pos = payload.get("plane_of_symmetry", False)
            if not isinstance(cc, int) or not isinstance(pos, bool):
                return {
                    "topic": "STEREOCHEMISTRY_V1",
                    "mode": "CHIRALITY",
                    "concept": "CHIRALITY / MESO",
                    "steps": "Need: chiral_centers (int) and plane_of_symmetry (bool).",
                    "answer": "INSUFFICIENT DATA",
                    "explanation": "Structured stereochemistry input is incomplete.",
                    "exam_tip": "Meso compounds have stereocenters but an internal plane of symmetry → achiral overall.",
                    "common_mistake": "Assuming any molecule with stereocenter is optically active (meso is not).",
                    "confidence": "PARTIAL",
                }

            out = _chirality_from_flags(chiral_centers=cc, plane_of_symmetry=pos)
            return {
                "topic": "STEREOCHEMISTRY_V1",
                "mode": "CHIRALITY",
                "concept": "CHIRALITY / MESO",
                "steps": "1) Count stereocenters.\n2) Check internal plane of symmetry.\n3) Conclude chiral / meso / achiral.",
                "answer": out["chirality"],
                "explanation": out["note"],
                "exam_tip": "Plane of symmetry overrides chirality: meso is achiral overall.",
                "common_mistake": "Marking meso as optically active.",
                "confidence": "DETERMINISTIC",
            }

        if subtask in ("optical", "optical_activity", "optically_active"):
            cc = payload.get("chiral_centers", 0)
            pos = payload.get("plane_of_symmetry", False)
            if not isinstance(cc, int) or not isinstance(pos, bool):
                return {
                    "topic": "STEREOCHEMISTRY_V1",
                    "mode": "OPTICAL_ACTIVITY",
                    "concept": "OPTICAL ACTIVITY",
                    "steps": "Need: chiral_centers (int) and plane_of_symmetry (bool).",
                    "answer": "INSUFFICIENT DATA",
                    "explanation": "Structured stereochemistry input is incomplete.",
                    "exam_tip": "Optical activity requires chirality and absence of internal compensation (meso).",
                    "common_mistake": "Marking meso as optically active.",
                    "confidence": "PARTIAL",
                }

            out = _chirality_from_flags(chiral_centers=cc, plane_of_symmetry=pos)
            if out["chirality"] == "CHIRAL":
                ans = "OPTICALLY ACTIVE"
                expl = "Chiral and no plane of symmetry indicated."
            else:
                ans = "OPTICALLY INACTIVE"
                expl = "Achiral overall (either no stereocenter or meso due to symmetry)."

            return {
                "topic": "STEREOCHEMISTRY_V1",
                "mode": "OPTICAL_ACTIVITY",
                "concept": "OPTICAL ACTIVITY",
                "steps": "1) Determine chirality.\n2) If meso/achiral → inactive; if chiral (no symmetry) → active.",
                "answer": ans,
                "explanation": expl,
                "exam_tip": "Meso compounds are optically inactive due to internal compensation.",
                "common_mistake": "Equating presence of stereocenter with optical activity (meso exception).",
                "confidence": "DETERMINISTIC",
            }

        # If payload exists but unknown subtask, fall to theory snippet
        return {
            "topic": "STEREOCHEMISTRY_V1",
            "mode": "THEORY",
            "answer": _THEORY_SNIPPETS["rs"],
        }

    # ---- 2) THEORY detection (text-only) ----
    if _has_any(low, ["define chirality", "what is chirality", "chiral", "achiral"]) and not _has_any(low, ["r-", "s-", "e-", "z-"]):
        return {
            "topic": "STEREOCHEMISTRY_V1",
            "mode": "THEORY",
            "answer": _THEORY_SNIPPETS["chirality"],
        }

    if _has_any(low, ["cahn", "ingold", "prelog", "cip", "assign r", "assign s", "r/s", "configuration r", "configuration s"]):
        return {
            "topic": "STEREOCHEMISTRY_V1",
            "mode": "THEORY",
            "answer": _THEORY_SNIPPETS["rs"],
        }

    if _has_any(low, ["e/z", "assign e", "assign z", "configuration e", "configuration z"]):
        return {
            "topic": "STEREOCHEMISTRY_V1",
            "mode": "THEORY",
            "answer": _THEORY_SNIPPETS["ez"],
        }

    if _has_any(low, ["meso"]):
        return {
            "topic": "STEREOCHEMISTRY_V1",
            "mode": "THEORY",
            "answer": _THEORY_SNIPPETS["meso"],
        }

    if _has_any(low, ["enantiomer", "diastereomer"]) and _has_any(low, ["difference", "distinguish", "between"]):
        return {
            "topic": "STEREOCHEMISTRY_V1",
            "mode": "THEORY",
            "answer": _THEORY_SNIPPETS["enantiomer_diastereo"],
        }

    # ---- 3) Small known-pair DB (text-only) ----
    if _has_any(low, ["d-lactic", "l-lactic"]) or (_has_any(low, ["d lactic", "l lactic"])):
        return {
            "topic": "STEREOCHEMISTRY_V1",
            "mode": "RS_ASSIGNMENT",
            "concept": "OPTICAL ISOMERISM (enantiomeric pair)",
            "steps": "D- and L- denote enantiomers for lactic acid in exam context.",
            "answer": "They are enantiomers (optical isomers).",
            "explanation": "D- and L- forms are non-superimposable mirror images.",
            "exam_tip": "Do not confuse D/L with R/S in general; D/L is a relative configuration notation.",
            "common_mistake": "Calling D/L directly as R/S without enough structural data.",
            "confidence": "PARTIAL",
        }

    return None
