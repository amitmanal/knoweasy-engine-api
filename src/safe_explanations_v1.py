# src/safe_explanations_v1.py
"""
KnowEasy Engine — Safe Explanations v1 (LOCKED)

Purpose:
- Generate student-facing explanations WITHOUT changing answers
- Deterministic: uses existing metadata only:
  - explainability.traces
  - explainability.tags
  - exam_policy (depth)
  - reason + assumptions

Strict rules:
- NO chemistry logic
- NO LLM / AI calls
- NO probabilistic content
- Output is derived solely from provided packet

Input expected:
- The unified response packet from response_packager_v1.build_response_packet()
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass(frozen=True)
class ExplanationV1:
    """
    Deterministic explanation output.
    """
    title: str
    steps: List[str] = field(default_factory=list)
    final: str = ""
    notes: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "title": self.title,
            "steps": list(self.steps),
            "final": self.final,
            "notes": list(self.notes),
        }


def _depth_to_step_limit(depth: str) -> int:
    d = (depth or "").strip().lower()
    if d == "short":
        return 2
    if d == "medium":
        return 4
    if d == "deep":
        return 8
    # safe default
    return 4


def _render_trace_step(trace: Dict[str, Any]) -> str:
    """
    Deterministically render a trace into a readable step.
    """
    rid = str(trace.get("rule_id", "")).strip() or "RULE"
    desc = str(trace.get("description", "")).strip() or "Applied rule"
    inputs = trace.get("inputs", {})
    outcome = trace.get("outcome", None)

    # Keep inputs compact, deterministic
    if isinstance(inputs, dict) and inputs:
        # stable order by key
        parts = [f"{k}={inputs[k]!r}" for k in sorted(inputs.keys())]
        inp_str = ", ".join(parts)
        base = f"{rid}: {desc} (inputs: {inp_str})"
    else:
        base = f"{rid}: {desc}"

    if outcome is not None:
        return f"{base} → {outcome!r}"
    return base


def generate_explanation_from_packet(packet: Dict[str, Any]) -> ExplanationV1:
    """
    Main entry: produce deterministic explanation for UI.

    Packet requirements (soft):
    - packet['answer']
    - packet['reason']
    - packet['exam_policy']['explanation_depth']
    - packet['explainability']['traces']
    - packet['assumptions']
    """
    answer = packet.get("answer")
    reason = str(packet.get("reason", "")).strip()
    exam_mode = str(packet.get("exam_mode", "BOARD")).strip()
    policy = packet.get("exam_policy", {}) or {}
    depth = str(policy.get("explanation_depth", "medium")).strip().lower()

    explain = packet.get("explainability", {}) or {}
    traces = explain.get("traces", []) or []
    tags = explain.get("tags", []) or []

    assumptions = packet.get("assumptions", []) or []
    errors = packet.get("errors", []) or []

    step_limit = _depth_to_step_limit(depth)

    # Build steps:
    steps: List[str] = []
    if isinstance(traces, list) and traces:
        for t in traces:
            if isinstance(t, dict):
                steps.append(_render_trace_step(t))
            # ignore unknown types deterministically
    else:
        # Fallback: reason-only step
        if reason:
            steps.append(f"Reason used: {reason}")

    # Apply depth limit (deterministic truncation)
    steps = steps[:step_limit]

    notes: List[str] = []
    if assumptions:
        notes.append("Assumptions: " + "; ".join(str(a) for a in assumptions))

    if tags:
        # keep compact
        notes.append("Tags: " + ", ".join(str(t) for t in tags[:10]))

    if errors:
        # show only categories, deterministic
        cats = []
        for e in errors:
            if isinstance(e, dict) and "category" in e:
                cats.append(str(e["category"]))
        if cats:
            notes.append("Risk signals: " + ", ".join(cats[:10]))

    title = f"Explanation ({exam_mode}, {depth})"
    final = f"Final Answer: {answer!r}"
    return ExplanationV1(title=title, steps=steps, final=final, notes=notes)


def attach_explanation_to_packet(packet: Dict[str, Any]) -> Dict[str, Any]:
    """
    Returns a copy of packet with:
      packet['explanation_v1'] = ExplanationV1.to_dict()
    """
    exp = generate_explanation_from_packet(packet).to_dict()
    out = dict(packet)
    out["explanation_v1"] = exp
    return out
