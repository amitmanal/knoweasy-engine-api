from __future__ import annotations
import json, logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger('knoweasy-engine-api')

try:
    from db import get_engine_safe
except Exception:
    def get_engine_safe():
        return None

try:
    from sqlalchemy import text as _sql_text
    def _t(q: str): return _sql_text(q)
except Exception:
    def _t(q: str): return q

def ensure_tables():
    engine = get_engine_safe()
    if not engine: return
    try:
        with engine.begin() as conn:
            conn.execute(_t("""
                CREATE TABLE IF NOT EXISTS luma_catalog (
                    id SERIAL PRIMARY KEY,
                    user_id INTEGER NOT NULL,
                    title TEXT NOT NULL,
                    doc_type TEXT NOT NULL DEFAULT 'link',
                    source TEXT NOT NULL DEFAULT 'user',
                    file_url TEXT NOT NULL,
                    file_key TEXT,
                    metadata_json TEXT NOT NULL DEFAULT '{}'::text,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                );
            """))
    except Exception as e:
        logger.exception(e)

# ---- REQUIRED EXPORTS (fix import error) ----
def get_content(*args, **kwargs):
    return None

def list_content(*args, **kwargs):
    return []
