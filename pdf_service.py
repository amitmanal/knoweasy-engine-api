"""pdf_service.py

Phase-4 deliverable: Premium, exam-safe PDF export for Answer-as-Learning-Object.

Design goals:
- Deterministic rendering (no HTML-to-PDF flakiness)
- Calm premium layout
- Works on Render (pure Python)
"""

from __future__ import annotations

from io import BytesIO
from datetime import datetime
from typing import Any, Dict

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen.canvas import Canvas


def _safe_text(v: Any) -> str:
    s = "" if v is None else str(v)
    return " ".join(s.replace("\r", " ").replace("\n", " ").split()).strip()


def _wrap_lines(text: str, max_chars: int) -> list[str]:
    text = _safe_text(text)
    if not text:
        return []
    words = text.split(" ")
    lines: list[str] = []
    cur: list[str] = []
    cur_len = 0
    for w in words:
        add = (1 if cur else 0) + len(w)
        if cur_len + add <= max_chars:
            cur.append(w)
            cur_len += add
        else:
            lines.append(" ".join(cur))
            cur = [w]
            cur_len = len(w)
    if cur:
        lines.append(" ".join(cur))
    return lines


def render_learning_object_pdf(lo: Dict[str, Any], *, brand: str = "KnowEasy", mode_label: str = "") -> bytes:
    """Render a Learning Object to PDF bytes."""

    buf = BytesIO()
    c = Canvas(buf, pagesize=A4)
    w, h = A4

    # Fonts: use built-in Helvetica (Render-safe). Keep it stable.
    title = _safe_text(lo.get("title") or "Answer")
    lang = _safe_text(lo.get("language") or "en").lower()
    date_str = _safe_text(lo.get("date") or datetime.utcnow().date().isoformat())
    mode = _safe_text(mode_label or lo.get("mode") or "")

    left = 18 * mm
    right = 18 * mm
    top = 18 * mm
    bottom = 18 * mm
    y = h - top

    def hr():
        nonlocal y
        c.setLineWidth(0.6)
        c.line(left, y, w - right, y)
        y -= 6

    def ensure_space(min_y: float = 70):
        nonlocal y
        if y < min_y:
            c.showPage()
            y = h - top

    # Header
    c.setFont("Helvetica-Bold", 16)
    for line in _wrap_lines(title, 72):
        c.drawString(left, y, line)
        y -= 20

    c.setFont("Helvetica", 9)
    meta_bits = [brand]
    if mode:
        meta_bits.append(mode)
    meta_bits.append(date_str)
    meta_bits.append(lang)
    c.drawString(left, y, " • ".join(meta_bits))
    y -= 10
    hr()

    def section(label: str, body: Any):
        nonlocal y
        body_txt = ""
        if isinstance(body, list):
            body_txt = "\n".join([_safe_text(x) for x in body if _safe_text(x)])
        elif isinstance(body, dict):
            body_txt = _safe_text(body)
        else:
            body_txt = _safe_text(body)
        if not body_txt:
            return
        ensure_space()
        c.setFont("Helvetica-Bold", 11)
        c.drawString(left, y, label)
        y -= 14
        c.setFont("Helvetica", 10)
        for para in body_txt.split("\n"):
            for line in _wrap_lines(para, 95):
                ensure_space()
                c.drawString(left, y, line)
                y -= 12
            y -= 4

    section("Why this matters", lo.get("why_this_matters"))

    # New schema: explanation_blocks (preferred)
    blocks = lo.get("explanation_blocks")
    if isinstance(blocks, list) and blocks:
        ensure_space()
        c.setFont("Helvetica-Bold", 12)
        c.drawString(left, y, "Explanation")
        y -= 14
        c.setFont("Helvetica", 10)
        for b in blocks:
            if isinstance(b, dict):
                bt = _safe_text(b.get("title") or "")
                bc = str(b.get("content") or "")
            else:
                bt = ""
                bc = str(b or "")
            if bt:
                c.setFont("Helvetica-Bold", 10)
                for line in _wrap_lines(bt, 105):
                    c.drawString(left, y, line)
                    y -= 12
                c.setFont("Helvetica", 10)
            for line in _wrap_lines(bc, 105):
                c.drawString(left, y, line)
                y -= 12
            y -= 4
        y -= 2
    else:
        # Back-compat: explanation (single text)
        section("Explanation", lo.get("explanation"))

    # Visuals (if present)
    visuals = lo.get("visuals")
    if isinstance(visuals, list) and visuals:
        ensure_space()
        c.setFont("Helvetica-Bold", 12)
        c.drawString(left, y, "Visuals")
        y -= 14
        c.setFont("Helvetica", 9)
        for v in visuals:
            if isinstance(v, dict):
                vt = _safe_text(v.get("title") or "")
                vcode = _safe_text(v.get("code") or "")
                vtype = _safe_text(v.get("type") or "")
                vfmt = _safe_text(v.get("format") or "")
            else:
                vt = ""
                vcode = _safe_text(v)
                vtype = ""
                vfmt = ""
            label = " — ".join([x for x in [vtype, vt, vfmt] if x])
            if label:
                c.setFont("Helvetica-Bold", 9)
                for line in _wrap_lines(label, 110):
                    c.drawString(left, y, line)
                    y -= 11
                c.setFont("Helvetica", 9)
            if vcode:
                for line in _wrap_lines(vcode, 110):
                    c.drawString(left, y, line)
                    y -= 11
            y -= 4
        y -= 2
    else:
        # Back-compat: visual_plan
        vp = lo.get("visual_plan")
        if vp:
            section("Visual plan", vp)

    section("Examples", lo.get("examples"))
    section("Common mistakes", lo.get("common_mistakes"))

    # Exam relevance footer (calm, honest)
    footer = _safe_text(lo.get("exam_relevance_footer") or "")
    if footer:
        ensure_space(90)
        hr()
        c.setFont("Helvetica", 9)
        for line in _wrap_lines(footer, 105):
            c.drawString(left, y, line)
            y -= 11

    c.showPage()
    c.save()
    return buf.getvalue()
