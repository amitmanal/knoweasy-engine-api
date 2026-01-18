"""Private internal cost dashboard endpoints (operator-only).

Enabled only when ADMIN_API_KEY is set.
Auth via header: X-Admin-Key.

Security posture:
- If ADMIN_API_KEY is missing/blank, behave like NOT FOUND (404).
- If key is wrong, return 403.

Read-only: does not modify user state.

This module queries ai_usage_logs directly via SQLAlchemy.
"""

from __future__ import annotations

import os
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Header, Query
from fastapi.responses import JSONResponse
from sqlalchemy import text

from db import _get_engine

router = APIRouter(prefix="/admin", tags=["admin"])


def _admin_key() -> str:
    return (os.getenv("ADMIN_API_KEY") or "").strip()


def _require_admin(x_admin_key: Optional[str]) -> None:
    key = _admin_key()
    # If not enabled, behave like it doesn't exist (security by obscurity).
    if not key:
        raise PermissionError("ADMIN_DISABLED")
    if not x_admin_key or x_admin_key.strip() != key:
        raise PermissionError("ADMIN_FORBIDDEN")


def _db_not_ready_payload() -> Dict[str, Any]:
    return {
        "ok": False,
        "enabled": False,
        "error": "DB_NOT_READY",
        "message": "DB is disabled or DATABASE_URL missing/invalid.",
    }


def _since_expr() -> str:
    """SQL snippet for filtering last N days.

    IMPORTANT: keep bind params parseable by SQLAlchemy.
    Avoid patterns like ":days::text" which can confuse the param parser
    and leak a literal ':' to Postgres (syntax error).

    Safe Postgres form: NOW() - (:days * INTERVAL '1 day')
    """

    return "(NOW() - (:days * INTERVAL '1 day'))"


@router.get("/cost/summary")
def cost_summary(
    days: int = Query(default=7, ge=1, le=365),
    x_admin_key: Optional[str] = Header(default=None, alias="X-Admin-Key"),
):
    """Aggregate requests/credits/cost over the last N days."""

    try:
        _require_admin(x_admin_key)
    except PermissionError as e:
        code = str(e)
        if code == "ADMIN_DISABLED":
            return JSONResponse(status_code=404, content={"ok": False, "error": "NOT_FOUND"})
        return JSONResponse(status_code=403, content={"ok": False, "error": "FORBIDDEN"})

    engine = _get_engine()
    if engine is None:
        return JSONResponse(status_code=200, content=_db_not_ready_payload())

    since = _since_expr()

    summary_sql = f"""
    SELECT
      COUNT(*)::int AS requests,
      COALESCE(SUM(CASE WHEN cache_hit THEN 1 ELSE 0 END),0)::int AS cache_hits,
      COALESCE(SUM(COALESCE(credits_charged,0)),0)::int AS credits_charged,
      COALESCE(SUM(COALESCE(tokens_in,0)),0)::int AS tokens_in,
      COALESCE(SUM(COALESCE(tokens_out,0)),0)::int AS tokens_out,
      COALESCE(SUM(COALESCE(estimated_cost_usd,0)),0) AS cost_usd,
      COALESCE(SUM(COALESCE(estimated_cost_inr,0)),0) AS cost_inr,
      COALESCE(AVG(COALESCE(latency_ms,0)),0)::int AS avg_latency_ms
    FROM ai_usage_logs
    WHERE created_at >= {since};
    """

    by_status_sql = f"""
    SELECT
      COALESCE(status,'UNKNOWN') AS status,
      COUNT(*)::int AS count
    FROM ai_usage_logs
    WHERE created_at >= {since}
    GROUP BY COALESCE(status,'UNKNOWN')
    ORDER BY count DESC;
    """

    by_model_sql = f"""
    SELECT
      COALESCE(model_primary,'UNKNOWN') AS model,
      COUNT(*)::int AS requests,
      COALESCE(SUM(CASE WHEN cache_hit THEN 1 ELSE 0 END),0)::int AS cache_hits,
      COALESCE(SUM(COALESCE(credits_charged,0)),0)::int AS credits_charged,
      COALESCE(SUM(COALESCE(estimated_cost_inr,0)),0) AS cost_inr
    FROM ai_usage_logs
    WHERE created_at >= {since}
    GROUP BY COALESCE(model_primary,'UNKNOWN')
    ORDER BY requests DESC;
    """

    try:
        with engine.connect() as conn:
            row = conn.execute(text(summary_sql), {"days": days}).mappings().first() or {}
            by_status = list(conn.execute(text(by_status_sql), {"days": days}).mappings().all())
            by_model = list(conn.execute(text(by_model_sql), {"days": days}).mappings().all())

        requests = int(row.get("requests") or 0)
        cache_hits = int(row.get("cache_hits") or 0)
        cache_hit_rate = (cache_hits / requests) if requests else 0.0

        out: Dict[str, Any] = {
            "ok": True,
            "days": days,
            "requests": requests,
            "cache_hits": cache_hits,
            "cache_hit_rate": round(cache_hit_rate, 4),
            "credits_charged": int(row.get("credits_charged") or 0),
            "tokens_in": int(row.get("tokens_in") or 0),
            "tokens_out": int(row.get("tokens_out") or 0),
            "estimated_cost_usd": float(row.get("cost_usd") or 0),
            "estimated_cost_inr": float(row.get("cost_inr") or 0),
            "avg_latency_ms": int(row.get("avg_latency_ms") or 0),
            "by_status": by_status,
            "by_model": by_model,
        }
        return JSONResponse(status_code=200, content=out)
    except Exception as ex:
        return JSONResponse(status_code=200, content={"ok": False, "error": "QUERY_FAILED", "message": str(ex)})


@router.get("/cost/top-users")
def cost_top_users(
    days: int = Query(default=7, ge=1, le=365),
    limit: int = Query(default=20, ge=1, le=200),
    x_admin_key: Optional[str] = Header(default=None, alias="X-Admin-Key"),
):
    """Top users by estimated cost over the last N days."""

    try:
        _require_admin(x_admin_key)
    except PermissionError as e:
        code = str(e)
        if code == "ADMIN_DISABLED":
            return JSONResponse(status_code=404, content={"ok": False, "error": "NOT_FOUND"})
        return JSONResponse(status_code=403, content={"ok": False, "error": "FORBIDDEN"})

    engine = _get_engine()
    if engine is None:
        return JSONResponse(status_code=200, content=_db_not_ready_payload())

    since = _since_expr()

    sql = f"""
    SELECT
      COALESCE(user_id, -1)::int AS user_id,
      COALESCE(role,'UNKNOWN') AS role,
      COALESCE(plan,'UNKNOWN') AS plan,
      COUNT(*)::int AS requests,
      COALESCE(SUM(CASE WHEN cache_hit THEN 1 ELSE 0 END),0)::int AS cache_hits,
      COALESCE(SUM(COALESCE(credits_charged,0)),0)::int AS credits_charged,
      COALESCE(SUM(COALESCE(estimated_cost_usd,0)),0) AS cost_usd,
      COALESCE(SUM(COALESCE(estimated_cost_inr,0)),0) AS cost_inr,
      COALESCE(MAX(created_at), NOW()) AS last_seen
    FROM ai_usage_logs
    WHERE created_at >= {since}
    GROUP BY COALESCE(user_id, -1), COALESCE(role,'UNKNOWN'), COALESCE(plan,'UNKNOWN')
    ORDER BY cost_inr DESC, requests DESC
    LIMIT :limit;
    """

    try:
        with engine.connect() as conn:
            rows: List[Dict[str, Any]] = list(
                conn.execute(text(sql), {"days": days, "limit": limit}).mappings().all()
            )

        for r in rows:
            if r.get("cost_usd") is not None:
                r["cost_usd"] = float(r["cost_usd"])
            if r.get("cost_inr") is not None:
                r["cost_inr"] = float(r["cost_inr"])

        return JSONResponse(status_code=200, content={"ok": True, "days": days, "limit": limit, "rows": rows})
    except Exception as ex:
        return JSONResponse(status_code=200, content={"ok": False, "error": "QUERY_FAILED", "message": str(ex)})
