-- Phase-2 Test Engine schema (additive only)
-- Safe to run multiple times.

CREATE TABLE IF NOT EXISTS tests (
  id SERIAL PRIMARY KEY,
  title VARCHAR(200) NOT NULL,
  description TEXT,
  cls INTEGER,
  board VARCHAR(100),
  subject_slug VARCHAR(120),
  chapter_slug VARCHAR(160),
  time_limit_sec INTEGER,
  total_marks INTEGER NOT NULL DEFAULT 0,
  is_published BOOLEAN NOT NULL DEFAULT FALSE,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS test_questions (
  id SERIAL PRIMARY KEY,
  test_id INTEGER NOT NULL REFERENCES tests(id) ON DELETE CASCADE,
  qno INTEGER NOT NULL,
  question_text TEXT NOT NULL,
  option_a TEXT NOT NULL,
  option_b TEXT NOT NULL,
  option_c TEXT NOT NULL,
  option_d TEXT NOT NULL,
  correct_option VARCHAR(1) NOT NULL,
  marks INTEGER NOT NULL DEFAULT 1,
  negative_marks INTEGER NOT NULL DEFAULT 0,
  explanation TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_test_questions_test_id ON test_questions(test_id);

CREATE TABLE IF NOT EXISTS test_attempts (
  id SERIAL PRIMARY KEY,
  user_id INTEGER NOT NULL,
  test_id INTEGER NOT NULL REFERENCES tests(id) ON DELETE CASCADE,
  status VARCHAR(16) NOT NULL DEFAULT 'STARTED',
  started_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  submitted_at TIMESTAMPTZ,
  time_taken_sec INTEGER,
  score INTEGER,
  max_score INTEGER,
  correct_count INTEGER,
  wrong_count INTEGER,
  skipped_count INTEGER
);

CREATE INDEX IF NOT EXISTS idx_test_attempts_user_id ON test_attempts(user_id);
CREATE INDEX IF NOT EXISTS idx_test_attempts_test_id ON test_attempts(test_id);

CREATE TABLE IF NOT EXISTS test_attempt_answers (
  id SERIAL PRIMARY KEY,
  attempt_id INTEGER NOT NULL REFERENCES test_attempts(id) ON DELETE CASCADE,
  question_id INTEGER NOT NULL REFERENCES test_questions(id) ON DELETE CASCADE,
  selected_option VARCHAR(1),
  is_correct BOOLEAN NOT NULL DEFAULT FALSE,
  marks_awarded INTEGER NOT NULL DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_test_attempt_answers_attempt_id ON test_attempt_answers(attempt_id);
