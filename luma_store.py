from __future__ import annotations
import json
import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger('knoweasy-engine-api')

try:
    from db import get_engine_safe
except Exception:
    def get_engine_safe():
        return None

try:
    from sqlalchemy import text as _sql_text
    def _t(q: str):
        return _sql_text(q)
except Exception:
    def _t(q: str):
        return q

def ensure_tables() -> None:
    engine = get_engine_safe()
    if not engine:
        logger.warning('DB unavailable')
        return
    try:
        with engine.begin() as conn:
            conn.execute(_t('''
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
            ''') )
            conn.execute(_t('''
                CREATE INDEX IF NOT EXISTS idx_luma_catalog_user_created
                ON luma_catalog(user_id, created_at DESC);
            ''') )
        logger.info('Tables ensured')
    except Exception as e:
        logger.exception(f'ensure_tables failed: {e}')
