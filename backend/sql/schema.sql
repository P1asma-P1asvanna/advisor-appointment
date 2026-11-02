-- Advisor Appointment — MVP schema (PostgreSQL)
-- 4 core tables: availability_slots, appointments, advising_notes, tasks
-- + minimal `users` table as a supporting reference (swap for your auth provider's users table)

CREATE EXTENSION IF NOT EXISTS btree_gist;
CREATE EXTENSION IF NOT EXISTS pgcrypto;

-- ---------- Supporting ----------
CREATE TABLE users (
  id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  email       TEXT NOT NULL UNIQUE,
  full_name   TEXT NOT NULL,
  role        TEXT NOT NULL CHECK (role IN ('advisor', 'student', 'admin')),
  department  TEXT,
  created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ---------- 1) availability_slots : advisor opens free time ----------
CREATE TABLE availability_slots (
  id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  advisor_id    UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  starts_at     TIMESTAMPTZ NOT NULL,
  ends_at       TIMESTAMPTZ NOT NULL,
  mode          TEXT NOT NULL DEFAULT 'onsite' CHECK (mode IN ('onsite', 'online')),
  location      TEXT,              -- room / office
  meeting_url   TEXT,              -- for online
  status        TEXT NOT NULL DEFAULT 'open' CHECK (status IN ('open', 'booked', 'cancelled')),
  created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
  CHECK (ends_at > starts_at),
  -- an advisor cannot have overlapping non-cancelled slots
  EXCLUDE USING gist (
    advisor_id WITH =,
    tstzrange(starts_at, ends_at) WITH &&
  ) WHERE (status <> 'cancelled')
);
CREATE INDEX idx_slots_advisor_time ON availability_slots (advisor_id, starts_at);
CREATE INDEX idx_slots_open ON availability_slots (starts_at) WHERE status = 'open';

-- ---------- 2) appointments : student books a slot ----------
CREATE TABLE appointments (
  id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  slot_id       UUID NOT NULL REFERENCES availability_slots(id),
  advisor_id    UUID NOT NULL REFERENCES users(id),
  student_id    UUID NOT NULL REFERENCES users(id),
  topic         TEXT NOT NULL,          -- what the student wants to discuss
  status        TEXT NOT NULL DEFAULT 'confirmed'
                CHECK (status IN ('pending', 'confirmed', 'cancelled', 'completed', 'no_show')),
  cancel_reason TEXT,
  cancelled_by  UUID REFERENCES users(id),
  created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);
-- prevents double booking: only one active appointment per slot
CREATE UNIQUE INDEX uq_active_appointment_per_slot
  ON appointments (slot_id) WHERE status IN ('pending', 'confirmed');
CREATE INDEX idx_appt_student ON appointments (student_id, created_at DESC);
CREATE INDEX idx_appt_advisor ON appointments (advisor_id, created_at DESC);

-- ---------- 3) advising_notes : record issues discussed ----------
CREATE TABLE advising_notes (
  id             UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  appointment_id UUID NOT NULL REFERENCES appointments(id) ON DELETE CASCADE,
  author_id      UUID NOT NULL REFERENCES users(id),
  issues         TEXT,                  -- ประเด็นที่ปรึกษา
  summary        TEXT,                  -- สรุป / ข้อตกลง
  visibility     TEXT NOT NULL DEFAULT 'shared' CHECK (visibility IN ('private', 'shared')),
                                        -- private = advisor only, shared = student can see
  created_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at     TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_notes_appt ON advising_notes (appointment_id);

-- ---------- 4) tasks : follow-up after the consultation ----------
CREATE TABLE tasks (
  id             UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  appointment_id UUID NOT NULL REFERENCES appointments(id) ON DELETE CASCADE,
  note_id        UUID REFERENCES advising_notes(id) ON DELETE SET NULL,
  assignee_id    UUID NOT NULL REFERENCES users(id),   -- usually the student
  created_by     UUID NOT NULL REFERENCES users(id),   -- usually the advisor
  title          TEXT NOT NULL,
  description    TEXT,
  due_date       DATE,
  status         TEXT NOT NULL DEFAULT 'todo' CHECK (status IN ('todo', 'doing', 'done', 'cancelled')),
  completed_at   TIMESTAMPTZ,
  created_at     TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_tasks_assignee ON tasks (assignee_id, status, due_date);
CREATE INDEX idx_tasks_appt ON tasks (appointment_id);

-- ---------- Booking helper (atomic, race-safe) ----------
-- Usage: SELECT book_slot(:slot_id, :student_id, :topic);
CREATE OR REPLACE FUNCTION book_slot(p_slot UUID, p_student UUID, p_topic TEXT)
RETURNS UUID LANGUAGE plpgsql AS $$
DECLARE
  v_advisor UUID;
  v_appt    UUID;
BEGIN
  SELECT advisor_id INTO v_advisor
  FROM availability_slots
  WHERE id = p_slot AND status = 'open' AND starts_at > now()
  FOR UPDATE;

  IF NOT FOUND THEN
    RAISE EXCEPTION 'slot_unavailable';
  END IF;

  INSERT INTO appointments (slot_id, advisor_id, student_id, topic)
  VALUES (p_slot, v_advisor, p_student, p_topic)
  RETURNING id INTO v_appt;

  UPDATE availability_slots SET status = 'booked' WHERE id = p_slot;
  RETURN v_appt;
END $$;
