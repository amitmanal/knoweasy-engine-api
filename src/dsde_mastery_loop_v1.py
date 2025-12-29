# src/dsde_mastery_loop_v1.py
"""
KnowEasy OS — DSDE ↔ Mastery Feedback Loop v1 (LOCKED)

Purpose:
- Deterministically adjust DSDE v1 plan using mastery scores
- Combine:
  1) Urgent needs from recent error patterns (DSDE v1 behavior)
  2) Long-term mastery gaps (Mastery Model)

Input:
- dsde_plan (output of dsde_v1.build_dsde_plan_v1)
- mastery_map:
    {
      "TAG": {"score": int, "state": str, ...}
    }

Output:
- updated plan with:
  - focus_tags refined
  - minutes rebalanced slightly (within deterministic limits)
  - extra reason appended

Rules (v1):
- If a focus_tag has mastery score < 40 => BOOST revise minutes by +10% (cap)
- If all focus_tags are mastered (>= 80) => SHIFT revise minutes -10% to test
- If plan contains "WEAK_AREA" placeholder => replace with lowest mastery tags

All deterministic, stable tie-breaks.
"""

from __future__ import annotations
from typing import Any, Dict, List, Tuple


def _clamp_int(v: int, lo: int, hi: int) -> int:
    return max(lo, min(hi, int(v)))


def _get_score(mastery_map: Dict[str, Any], tag: str) -> int:
    rec = mastery_map.get(tag)
    if isinstance(rec, dict):
        try:
            return int(rec.get("score", 0))
        except Exception:
            return 0
    return 0


def _lowest_mastery_tags(mastery_map: Dict[str, Any], k: int = 3) -> List[str]:
    items: List[Tuple[int, str]] = []
    for tag, rec in (mastery_map or {}).items():
        if not isinstance(tag, str) or not tag.strip():
            continue
        score = _get_score(mastery_map, tag)
        items.append((score, tag))
    # deterministic: sort by score asc, then tag asc
    items.sort(key=lambda x: (x[0], x[1]))
    return [t for _, t in items[:k]]


def apply_mastery_feedback_v1(
    *,
    dsde_plan: Dict[str, Any],
    mastery_map: Dict[str, Any],
) -> Dict[str, Any]:
    if not isinstance(dsde_plan, dict):
        raise ValueError("dsde_plan must be a dict")
    if not isinstance(mastery_map, dict):
        raise ValueError("mastery_map must be a dict")

    plan = dict(dsde_plan)
    blocks = list(plan.get("blocks") or [])
    if len(blocks) < 3:
        # keep stable; do nothing
        plan["mastery_feedback_note"] = "No change: unexpected block structure."
        return plan

    # Identify revise + test blocks deterministically by position (DSDE v1 contract)
    revise = dict(blocks[0])
    test = dict(blocks[1])
    learn = dict(blocks[2])

    focus_tags = list(revise.get("focus_tags") or [])
    focus_tags = [str(t) for t in focus_tags if str(t).strip()]

    # Replace WEAK_AREA placeholder with lowest mastery tags
    if "WEAK_AREA" in focus_tags or not focus_tags:
        repl = _lowest_mastery_tags(mastery_map, k=3)
        if repl:
            focus_tags = repl
        else:
            focus_tags = ["FOUNDATION"]

    # Compute mastery status over focus tags
    scores = [_get_score(mastery_map, t) for t in focus_tags]
    has_low = any(s < 40 for s in scores) if scores else False
    all_mastered = all(s >= 80 for s in scores) if scores else False

    # Minute rebalancing (deterministic, gentle)
    revise_min = int(revise.get("minutes", 0))
    test_min = int(test.get("minutes", 0))
    learn_min = int(learn.get("minutes", 0))
    total = revise_min + test_min + learn_min

    note_parts: List[str] = []
    if has_low:
        # boost revise by +10% of revise minutes, taken from test (preferred) then learn
        boost = max(1, int(round(revise_min * 0.10)))
        take_from_test = min(boost, max(0, test_min - 10))  # keep at least 10 min
        remaining = boost - take_from_test
        take_from_learn = min(remaining, max(0, learn_min - 10))  # keep at least 10 min

        revise_min += (take_from_test + take_from_learn)
        test_min -= take_from_test
        learn_min -= take_from_learn

        note_parts.append("Boosted REVISE due to low mastery tags (<40).")

    elif all_mastered:
        # shift 10% of revise to test
        shift = max(1, int(round(revise_min * 0.10)))
        shift = min(shift, max(0, revise_min - 10))  # keep at least 10
        revise_min -= shift
        test_min += shift
        note_parts.append("Shifted time from REVISE to TEST because focus tags are mastered (>=80).")

    # Clamp minutes to keep stable and preserve total
    revise_min = _clamp_int(revise_min, 10, total)
    test_min = _clamp_int(test_min, 10, total)
    learn_min = _clamp_int(learn_min, 10, total)

    # Fix any drift deterministically by adjusting revise block
    drift = total - (revise_min + test_min + learn_min)
    revise_min += drift

    # Write back
    revise["minutes"] = revise_min
    test["minutes"] = test_min
    learn["minutes"] = learn_min
    revise["focus_tags"] = focus_tags

    # Add mastery context to reason
    revise_reason = str(revise.get("reason", "")).strip()
    mastery_hint = f"Mastery scores: " + ", ".join(f"{t}={_get_score(mastery_map,t)}" for t in focus_tags[:5])
    revise["reason"] = (revise_reason + " " + mastery_hint).strip()

    blocks2 = [revise, test, learn]
    plan["blocks"] = blocks2

    base_reason = str(plan.get("reason", "")).strip()
    feedback_note = " ".join(note_parts) if note_parts else "No minutes shift; mastery within normal range."
    plan["reason"] = (base_reason + " " + feedback_note).strip()
    plan["mastery_feedback_note"] = feedback_note
    plan["version"] = "dsde_mastery_loop_v1"
    return plan
