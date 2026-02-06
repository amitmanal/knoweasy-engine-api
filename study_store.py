from sqlalchemy import create_engine, text
import os

DATABASE_URL = os.getenv("DATABASE_URL")
engine = create_engine(DATABASE_URL, pool_pre_ping=True)

def ensure_tables():
    with engine.begin() as conn:
        conn.execute(text("""
        CREATE TABLE IF NOT EXISTS syllabus_nodes (
            id SERIAL PRIMARY KEY,
            track TEXT NOT NULL,
            program TEXT NOT NULL,
            class_level INT NOT NULL,
            subject_code TEXT NOT NULL,
            chapter_slug TEXT NOT NULL,
            chapter_title TEXT NOT NULL,
            sort_order INT DEFAULT 0,
            is_published BOOLEAN DEFAULT TRUE,
            created_at TIMESTAMP DEFAULT NOW(),
            updated_at TIMESTAMP DEFAULT NOW(),
            UNIQUE(track, program, class_level, subject_code, chapter_slug)
        );
        """))

def reset_syllabus():
    with engine.begin() as conn:
        conn.execute(text("TRUNCATE syllabus_nodes RESTART IDENTITY CASCADE;"))

def seed_syllabus(rows):
    ensure_tables()
    inserted = 0
    with engine.begin() as conn:
        for row in rows:
            result = conn.execute(text("""
                INSERT INTO syllabus_nodes
                (track, program, class_level, subject_code,
                 chapter_slug, chapter_title, sort_order)
                VALUES
                (:track, :program, :class_level, :subject_code,
                 :chapter_slug, :chapter_title, :sort_order)
                ON CONFLICT DO NOTHING;
            """), row)
            inserted += result.rowcount
    return inserted

def get_syllabus(track, program, class_level, subject_code):
    ensure_tables()
    with engine.begin() as conn:
        result = conn.execute(text("""
            SELECT chapter_slug, chapter_title, sort_order
            FROM syllabus_nodes
            WHERE track = :track
              AND program = :program
              AND class_level = :class_level
              AND subject_code = :subject_code
              AND is_published = TRUE
            ORDER BY sort_order ASC;
        """), {
            "track": track,
            "program": program,
            "class_level": class_level,
            "subject_code": subject_code
        })
        return [dict(row) for row in result]
