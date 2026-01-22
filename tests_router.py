from __future__ import annotations

import json
import logging
import os
import time
from typing import Any, Dict, Optional

from fastapi import APIRouter, Request, Header
from fastapi.responses import JSONResponse

from tests_schemas import TestGenerateRequest, GeneratedTest
from ai_router import generate_json as generate_ai_json

from auth_store import session_user
from payments_store import get_subscription
import billing_store
from redis_store import setnx_ex as redis_setnx_ex, incr_with_ttl as redis_incr_with_ttl, get_json as redis_get_json, setex_json as redis_setex_json

logger = logging.getLogger("knoweasy.tests_router")

router = APIRouter(prefix="/test", tags=["tests"])

def _client_ip(request: Request) -> str:
    xff = request.headers.get('x-forwarded-for') or request.headers.get('X-Forwarded-For')
    if xff:
        return xff.split(',')[0].strip()
    try:
        return request.client.host if request.client else 'unknown'
    except Exception:
        return 'unknown'



def _auth_user(authorization: Optional[str]) -> Optional[Dict[str, Any]]:
    if not authorization:
        return None
    token = authorization.strip()
    if token.lower().startswith("bearer "):
        token = token[7:].strip()
    if not token:
        return None
    try:
        return session_user(token)
    except Exception:
        return None


def _credits_for(kind: str, n_questions: int) -> int:
    # Simple, transparent defaults. Tune later via env without redeploy.
    base = int(os.getenv("CREDITS_TEST_BASE", "2"))
    per_10q = int(os.getenv("CREDITS_TEST_PER_10Q", "1"))
    if kind == "entrance":
        base = int(os.getenv("CREDITS_TEST_ENTRANCE_BASE", str(base + 1)))
    # scale with size
    units = base + (max(0, int(n_questions) - 10) // 10) * per_10q
    return max(1, min(10, units))


def _build_prompt(req: TestGenerateRequest) -> str:
    """
    Build a prompt instructing the AI to generate a paper in the v2 schema.

    The v2 schema contains a top-level paper with sections and rich option objects.  It
    replaces the older flat `questions` list so that the frontend player can render
    sections and questions consistently.  The prompt asks the provider to strictly
    adhere to the JSON format and to avoid any markdown or commentary.
    """
    # Determine exam context overlay for style/difficulty hints.  Even when generating
    # board-level questions, the exam overlay affects tone and depth (e.g. JEE
    # requires tougher problems).  The underlying syllabus remains the board syllabus.
    goal_map = {
        "NONE": "boards",
        "BOARD": "boards",
        "JEE_PCM": "jee_pcm",
        "NEET_PCB": "neet_pcb",
        "CET_PCM": "cet_pcm",
        "CET_PCB": "cet_pcb",
    }
    g = goal_map.get(str(req.goal).upper(), "boards")
    exam_context = {
        "jee_pcm": "JEE (PCM)",
        "neet_pcb": "NEET (PCB)",
        "cet_pcm": "CET (PCM)",
        "cet_pcb": "CET (PCB)",
        "boards": "Board Exam",
    }.get(g, "Board Exam")

    # Determine mode (quiz/boards/entrance) from kind.  Existing API uses `kind`.
    mode = str(req.kind or "quiz").lower()
    if mode not in {"quiz", "boards", "entrance"}:
        mode = "quiz"

    # Number of questions to ask for; default to req.n_questions.
    n_questions = int(req.n_questions or 10)

    # Duration hints: shorter for quizzes, medium for boards, longer for entrance.  Use
    # reasonable defaults in seconds.  The provider may override but should follow the
    # hint.
    # Duration hints: quick quizzes are very short, subject (boards) tests
    # mid‑length, and entrance tests full‑length.  Provide generous
    # examination durations so AI can calibrate the paper.
    if mode == "quiz":
        duration_sec = 10 * 60  # 10 minutes
    elif mode == "boards":
        duration_sec = 90 * 60  # 1.5 hours
    else:
        duration_sec = 180 * 60  # 3 hours

    # Marking scheme: for quiz/boards: 1 mark per correct, no penalty; for entrance,
    # include negative marking.  Clients can adjust on submission.
    if mode == "entrance":
        marking = {"correct": 4, "wrong": -1, "unattempted": 0}
    else:
        marking = {"correct": 1, "wrong": 0, "unattempted": 0}

    # Chapter focus description for the prompt.  If chapters list is empty, instruct to
    # mix content from the entire subject syllabus.
    if req.chapters:
        chapters_desc = ", ".join(req.chapters)
    else:
        chapters_desc = "mixed from the subject syllabus"

    # Difficulty hint – this is passed through from the request but capped to the
    # allowed values in tests_schemas.  The provider should interpret it at its
    # discretion.
    difficulty = str(req.difficulty or "mixed")

    # Language hint – helps the provider translate the output if needed.
    language = str(req.language or "en")

    # Build the strict JSON schema description that the model must follow.  We insert
    # example values to guide the provider.  Comments are kept outside the JSON block.
    schema_json = {
        "id": "string",
        "title": "string",
        "mode": "quiz|boards|entrance",
        "class_n": req.class_n,
        "board": req.board,
        "goal": g,
        "subject": req.subject,
        "chapters": req.chapters or [],
        "duration_sec": duration_sec,
        "marking": marking,
        "sections": [
            {
                "name": "Section",
                "questions": [
                    {
                        "id": "q1",
                        "text": "Question text",
                        "options": [
                            {"key": "A", "text": "..."},
                            {"key": "B", "text": "..."},
                            {"key": "C", "text": "..."},
                            {"key": "D", "text": "..."},
                        ],
                        "answerKey": "A",
                        "explanation": "short teacher explanation",
                        "tags": {"chapter": ""}
                    }
                ]
            }
        ]
    }

    prompt_lines = [
        "You are an expert teacher and exam question setter.",
        "Return ONLY valid JSON (no markdown, no extra text). Follow this schema exactly:",
        json.dumps(schema_json),
        "Rules:",
        f"- Create exactly {n_questions} multiple-choice questions with four options each.",
        "- Answer keys MUST be one of \"A\", \"B\", \"C\", or \"D\".",
        f"- Questions must align with Class {req.class_n} {req.board.upper()} syllabus level for subject {req.subject}.",
        f"- Focus on chapters: {chapters_desc}.",
        f"- Difficulty: {difficulty}.",
        f"- Exam context overlay: {exam_context}. Only changes style/depth, not base syllabus.",
        f"- Language: {language}. Translate the question, options and explanation if not English.",
        "- Provide clear, concise explanations (2–3 sentences).",
        "- Use a unique ID for each question and for the paper.",
        "- Title should be meaningful and relevant.",
    ]
    return "\n".join(prompt_lines)


@router.post("/generate")
async def generate_test(
    request: Request,
    authorization: Optional[str] = Header(default=None),
):
    """Generate a test JSON for the Tests page.

    TRUST RULES:
    - Never consume credits unless we are returning a real generated test.
    - Retries must not double-charge: if request_id is present, we replay.
    - Guests are allowed for Phase-1 stability, but are rate-limited.
    """
    t0 = time.time()
    try:
        payload = await request.json()
    except Exception:
        payload = {}

    try:
        req = TestGenerateRequest(**(payload or {}))
    except Exception as e:
        return JSONResponse(status_code=400, content={"ok": False, "error": "BAD_REQUEST", "message": str(e)})

    user_ctx = _auth_user(authorization)
    sub = None
    plan = "free"
    user_id: int | None = None
    if user_ctx:
        try:
            user_id = int(user_ctx.get("user_id"))
        except Exception:
            user_id = None
        try:
            sub = get_subscription(int(user_id)) if user_id is not None else None
        except Exception:
            sub = None
        try:
            plan = (sub or {}).get("plan") or "free"
        except Exception:
            plan = "free"

    # ---------------- Idempotency (replay) ----------------
    request_id = (req.request_id or "").strip() or None
    if request_id:
        replay_key = f"rid:testgen:{request_id}"
        try:
            prior = redis_get_json(replay_key)
            if isinstance(prior, dict) and prior.get("ok") and prior.get("test"):
                return prior
        except Exception:
            pass

        # lock to avoid rare parallel double-processing for same request_id
        try:
            lock_key = f"lock:rid:testgen:{request_id}"
            got_lock = redis_setnx_ex(lock_key, 30, value="1")
            if not got_lock:
                time.sleep(0.25)
                prior2 = redis_get_json(replay_key)
                if isinstance(prior2, dict) and prior2.get("ok") and prior2.get("test"):
                    return prior2
        except Exception:
            pass

    # ---------------- Guest rate-limit (cost control) ----------------
    if not user_id:
        ip = _client_ip(request)
        limit = int(os.getenv("GUEST_TESTGEN_PER_HOUR", "6"))
        key = f"rl:testgen:{ip}:{int(time.time() // 3600)}"
        try:
            c = redis_incr_with_ttl(key, 3600)
            if c is not None and c > limit:
                return JSONResponse(
                    status_code=429,
                    content={
                        "ok": False,
                        "error": "RATE_LIMITED",
                        "message": "Too many test generations right now. Please login or try again later.",
                    },
                )
        except Exception:
            # If Redis is down, proceed (Phase-1 stability)
            pass

    # ---------------- Credits (preview only) ----------------
    credits_units = _credits_for(req.kind, req.n_questions)
    if user_id:
        try:
            w_preview = billing_store.get_wallet(int(user_id), str(plan))
            total_preview = int(w_preview.get("included_credits_balance") or 0) + int(w_preview.get("booster_credits_balance") or 0)
            if total_preview < int(credits_units):
                return JSONResponse(
                    status_code=402,
                    content={
                        "ok": False,
                        "error": "INSUFFICIENT_CREDITS",
                        "message": "You have used all your AI credits. Please buy a Booster Pack or upgrade your plan.",
                        "required_credits": int(credits_units),
                    },
                )
        except ValueError:
            return JSONResponse(
                status_code=402,
                content={
                    "ok": False,
                    "error": "INSUFFICIENT_CREDITS",
                    "message": "You have used all your AI credits. Please buy a Booster Pack or upgrade your plan.",
                    "required_credits": int(credits_units),
                },
            )
        except Exception:
            # Billing preview failure must not block learning (stability first)
            pass

    # ---------------- AI generation ----------------
    prompt = _build_prompt(req)
    paper: Dict[str, Any]
    try:
        out = generate_ai_json(prompt)
        if not out:
            raise ValueError("Empty AI response")
        paper = dict(out)

        # Ensure `sections` exists. If only `questions` exists (old format), convert.
        if "sections" not in paper and "questions" in paper:
            qs = paper.get("questions") or []
            section = {"name": "Section", "questions": []}
            for i, q in enumerate(qs):
                try:
                    qid = q.get("id") or f"q{i+1}"
                    text = q.get("question") or q.get("text") or ""
                    options = q.get("options") or []
                    # Convert ["A", "B"] -> [{key:"A", text:"A"}, ...]
                    opt_objs = []
                    for j, opt in enumerate(options):
                        key = chr(ord("A") + j)
                        opt_objs.append({"key": key, "text": str(opt)})
                    ans_idx = q.get("answer_index")
                    ans_key = chr(ord("A") + int(ans_idx)) if isinstance(ans_idx, int) and 0 <= ans_idx < len(opt_objs) else ""
                    section["questions"].append({
                        "id": str(qid),
                        "type": "mcq",
                        "stem": str(text),
                        "options": opt_objs,
                        "answerKey": ans_key,
                        "explanation": q.get("explanation") or "",
                        "tags": {"subject": req.subject or "", "chapter": (req.chapters[0] if req.chapters else "")},
                    })
                except Exception:
                    continue
            paper = {
                "title": paper.get("title") or f"{req.subject} Test",
                "duration_minutes": int(paper.get("duration_minutes") or 30),
                "marking": paper.get("marking") or {"correct": 1, "wrong": 0, "unattempted": 0},
                "sections": [section],
            }

        # Minimal validation
        if not isinstance(paper.get("sections"), list) or not paper.get("sections"):
            raise ValueError("Paper schema invalid (missing sections)")

    except Exception as e:
        # IMPORTANT: do not consume credits on AI failure
        return JSONResponse(
            status_code=502,
            content={"ok": False, "error": "AI_FAILED", "message": "Could not generate test right now. Please try again."},
        )

    # ---------------- Consume credits ONLY after success ----------------
    wallet_after = None
    if user_id:
        try:
            wallet_after = billing_store.consume_credits(
                user_id=int(user_id),
                plan=str(plan),
                units=int(credits_units),
                meta={
                    "feature": "TEST_GENERATE",
                    "kind": req.kind,
                    "class_n": req.class_n,
                    "board": req.board,
                    "subject": req.subject,
                    "n_questions": req.n_questions,
                    "request_id": request_id,
                },
            )
        except ValueError:
            # Edge race: credits spent in another request after preview.
            return JSONResponse(
                status_code=402,
                content={
                    "ok": False,
                    "error": "INSUFFICIENT_CREDITS",
                    "message": "You have used all your AI credits. Please buy a Booster Pack or upgrade your plan.",
                    "required_credits": int(credits_units),
                },
            )
        except Exception:
            # DB down: allow, but don't claim wallet numbers.
            wallet_after = None

    meta = {
        "generated_ms": int((time.time() - t0) * 1000),
        "credits_charged": int(credits_units) if user_id else 0,
        "wallet": wallet_after,
        "plan": str(plan),
        "auth": bool(user_id),
    }

    resp = {"ok": True, "test": paper, "meta": meta}

    # Persist replay cache (best-effort)
    if request_id:
        try:
            redis_setex_json(f"rid:testgen:{request_id}", 10 * 60, resp)
        except Exception:
            pass

    return resp
@router.post("/submit")
async def submit_test(request: Request):
    """
    Evaluate a submitted test locally by comparing provided answers with the correct
    answer key embedded in the paper.  This endpoint does not require
    authentication or credits.  It returns a score breakdown and per-question
    status so that the client can render the result and explanations.

    Expected input JSON:
    {
      "paper": { ...paper schema as returned by /test/generate... },
      "answers": { "q1": "A", "q2": "C", ... }
    }
    """
    try:
        payload = await request.json()
    except Exception:
        return JSONResponse(status_code=400, content={"ok": False, "error": "BAD_REQUEST", "message": "Invalid JSON payload"})

    paper = payload.get("paper")
    answers = payload.get("answers") or {}
    if not paper or "sections" not in paper:
        return JSONResponse(status_code=400, content={"ok": False, "error": "INVALID_PAPER", "message": "Paper missing or invalid"})

    # Flatten questions
    questions = []
    for sec in paper.get("sections") or []:
        for q in sec.get("questions") or []:
            questions.append(q)

    correct = 0
    wrong = 0
    unattempted = 0
    details = []
    for q in questions:
        qid = q.get("id")
        ans = answers.get(str(qid))
        correct_key = str(q.get("answerKey")).strip().upper() if q.get("answerKey") else ""
        is_correct = ans and str(ans).strip().upper() == correct_key
        if not ans:
            unattempted += 1
        elif is_correct:
            correct += 1
        else:
            wrong += 1
        details.append({
            "qid": qid,
            "answer": ans,
            "correctKey": correct_key,
            "isCorrect": bool(is_correct),
            "explanation": q.get("explanation") or "",
        })

    # Marking scheme from paper (default to +1/0/0)
    marking = paper.get("marking") or {}
    m_correct = int(marking.get("correct", 1) or 0)
    m_wrong = int(marking.get("wrong", 0) or 0)
    m_unattempted = int(marking.get("unattempted", 0) or 0)

    score = correct * m_correct + wrong * m_wrong + unattempted * m_unattempted

    return {
        "ok": True,
        "result": {
            "correct": correct,
            "wrong": wrong,
            "unattempted": unattempted,
            "score": score,
            "details": details,
        },
    }


@router.get("/pyq/list")
async def list_pyq():
    """
    Return the list of available PYQ papers.  Reads from the `exams/index.json` file
    located alongside this module.  If the file is missing, returns an empty list
    with a `demo` flag to indicate that the client should show a demo paper.
    """
    import os, json
    base_dir = os.path.join(os.path.dirname(__file__), "exams")
    index_path = os.path.join(base_dir, "index.json")
    try:
        with open(index_path, "r", encoding="utf-8") as f:
            data = json.load(f)
            if isinstance(data, dict) and "papers" in data:
                return {"papers": data.get("papers", []), "demo": False}
    except Exception:
        pass
    # fallback
    return {"papers": [], "demo": True}


@router.get("/pyq/paper")
async def get_pyq_paper(path: str):
    """
    Return the full PYQ paper JSON given a relative path (as advertised in
    `/pyq/list`).  If the file is missing or invalid, return a demo paper.

    Query params:
      path: relative path under the exams directory, e.g. "jee_main/2024/jan_shift1/paper.json".
    """
    import os, json
    base_dir = os.path.join(os.path.dirname(__file__), "exams")
    # Prevent directory traversal by normalising and ensuring the path stays within base
    safe_path = os.path.normpath(path or "").lstrip(os.sep)
    file_path = os.path.join(base_dir, safe_path)
    try:
        # Verify that the resolved path starts with the exams base directory
        if not os.path.commonprefix([os.path.realpath(file_path), os.path.realpath(base_dir)]) == os.path.realpath(base_dir):
            raise ValueError("Invalid path")
        with open(file_path, "r", encoding="utf-8") as f:
            paper = json.load(f)
            return {"paper": paper, "demo": False}
    except Exception:
        # Demo fallback: minimal paper with one question
        demo_paper = {
            "id": "demo_pyq", 
            "title": "PYQ Simulation (Demo)",
            "durationSec": 1800,
            "marking": {"correct": 4, "wrong": -1, "unattempted": 0},
            "sections": [
                {
                    "name": "Demo Section",
                    "questions": [
                        {
                            "id": "d1",
                            "text": "Demo PYQ question: What is 2 + 2?",
                            "options": [
                                {"key": "A", "text": "3"},
                                {"key": "B", "text": "4"},
                                {"key": "C", "text": "5"},
                                {"key": "D", "text": "None"},
                            ],
                            "answerKey": "B",
                            "explanation": "2 + 2 equals 4.",
                            "tags": {"subject": "General", "chapter": "Demo", "year": None},
                        }
                    ],
                }
            ],
        }
        return {"paper": demo_paper, "demo": True}


# ------------------- Analysis Endpoint -------------------
# ------------------- Analysis Endpoint -------------------
@router.post("/analyze")
async def analyze_test(request: Request, authorization: Optional[str] = Header(default=None)):
    """AI-powered analysis of a test result.

    SECURITY / COST RULES:
    - Always return stats (local computation) for everyone.
    - Only call AI analysis if the user is authenticated AND has credits.
    - Never consume credits unless the AI analysis succeeded.
    - Guests are rate-limited (even though we won't call AI for them).
    """
    try:
        data = await request.json()
    except Exception:
        return JSONResponse(status_code=400, content={"ok": False, "error": "BAD_REQUEST", "message": "Invalid JSON"})

    paper = data.get("paper") or {}
    answers = data.get("answers") or {}
    result = data.get("result")

    if not paper or "sections" not in paper:
        return JSONResponse(status_code=400, content={"ok": False, "error": "INVALID_PAPER", "message": "Paper missing or invalid"})

    # If a full result is not provided, compute it locally
    if result is None:
        questions = []
        for sec in paper.get("sections") or []:
            for q in sec.get("questions") or []:
                questions.append(q)

        correct = 0
        wrong = 0
        unattempted = 0
        details = []
        for q in questions:
            qid = q.get("id")
            ans = answers.get(str(qid))
            correct_key = str(q.get("answerKey") or "").strip().upper()
            is_correct = ans and str(ans).strip().upper() == correct_key
            if not ans:
                unattempted += 1
            elif is_correct:
                correct += 1
            else:
                wrong += 1
            details.append({
                "qid": qid,
                "answer": ans,
                "correctKey": correct_key,
                "isCorrect": bool(is_correct),
                "explanation": q.get("explanation") or "",
                "chapter": (q.get("tags") or {}).get("chapter") or ""
            })
        result = {"correct": correct, "wrong": wrong, "unattempted": unattempted, "details": details}
    else:
        # Ensure details contain chapter info
        for d in result.get("details") or []:
            if "chapter" not in d:
                qid = d.get("qid")
                for sec in paper.get("sections") or []:
                    for q in sec.get("questions") or []:
                        if str(q.get("id")) == str(qid):
                            d["chapter"] = (q.get("tags") or {}).get("chapter") or ""
                            break

    # Compute per-chapter stats
    stats: Dict[str, Dict[str, int]] = {}
    for det in result.get("details") or []:
        chap_raw = (det.get("chapter") or "").strip()
        chap = chap_raw.title() if chap_raw else "General"
        if chap not in stats:
            stats[chap] = {"total": 0, "correct": 0, "wrong": 0, "unattempted": 0}
        stats[chap]["total"] += 1
        ans = det.get("answer")
        if ans is None or ans == "" or ans == "—":
            stats[chap]["unattempted"] += 1
        elif det.get("isCorrect"):
            stats[chap]["correct"] += 1
        else:
            stats[chap]["wrong"] += 1

    # ---- Auth + credits gate for AI analysis ----
    user_ctx = _auth_user(authorization)
    if not user_ctx:
        # Guest: return stats only (no AI)
        return {"ok": True, "stats": stats, "analysis": ""}

    try:
        user_id = int(user_ctx.get("user_id"))
    except Exception:
        return {"ok": True, "stats": stats, "analysis": ""}

    # Determine plan (best-effort)
    plan = "free"
    try:
        sub = get_subscription(user_id)
        plan = (sub or {}).get("plan") or "free"
    except Exception:
        plan = "free"

    # Credits needed (small, fixed)
    units = int(os.getenv("CREDITS_TEST_ANALYZE", "1"))

    # Preview wallet (fail fast)
    try:
        w_preview = billing_store.get_wallet(user_id, str(plan))
        total_preview = int(w_preview.get("included_credits_balance") or 0) + int(w_preview.get("booster_credits_balance") or 0)
        if total_preview < units:
            return JSONResponse(
                status_code=402,
                content={
                    "ok": False,
                    "error": "INSUFFICIENT_CREDITS",
                    "message": "You have used all your AI credits. Please buy a Booster Pack or upgrade your plan.",
                    "stats": stats,
                    "analysis": "",
                },
            )
    except Exception:
        # If preview fails, do not block; we will only charge on success.
        pass

    # Build summary for AI
    summary_lines = []
    for ch, st in stats.items():
        summary_lines.append(f"{ch}: {st['correct']} correct, {st['wrong']} wrong, {st['unattempted']} unattempted out of {st['total']}")
    summary = "; ".join(summary_lines)

    prompt = (
        "You are a senior teacher and mentor. A student took a test and here is their chapter-wise performance: "
        + summary
        + ". Provide a concise analysis highlighting strengths and weaknesses. Mention chapters they did well in and chapters to improve. Offer 2-3 actionable study suggestions. Return plain text (no JSON, no markdown)."
    )

    analysis_text = ""
    try:
        analysis_resp = generate_ai_json(prompt)
        if isinstance(analysis_resp, dict):
            analysis_text = analysis_resp.get("analysis") or analysis_resp.get("text") or ""
            if not analysis_text:
                for v in analysis_resp.values():
                    if isinstance(v, str):
                        analysis_text = v
                        break
        elif isinstance(analysis_resp, str):
            analysis_text = analysis_resp
        analysis_text = str(analysis_text or "").strip()
    except Exception:
        analysis_text = ""

    # Charge credits ONLY if we produced a non-empty analysis
    if analysis_text:
        try:
            billing_store.consume_credits(
                user_id=user_id,
                plan=str(plan),
                units=int(units),
                meta={"feature": "TEST_ANALYZE"},
            )
        except Exception:
            # Never block returning the analysis due to billing write failure.
            pass

    return {"ok": True, "stats": stats, "analysis": analysis_text}
