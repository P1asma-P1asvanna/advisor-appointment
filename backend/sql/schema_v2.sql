-- Advisor Appointment — schema v2 (additive migration on top of schema.sql)
-- Adds: booking_policies, notifications, policy-aware book_slot(), cancel_appointment(),
--       send_reminders() (run hourly by a scheduler), and v_advisor_stats for the department dashboard.

-- ---------- booking_policies : rules set by department staff ----------
CREATE TABLE booking_policies (
  department              TEXT PRIMARY KEY,            -- '*' = default for every department
  min_notice_hours        INT NOT NULL DEFAULT 12 CHECK (min_notice_hours >= 0),
  cancel_before_hours     INT NOT NULL DEFAULT 12 CHECK (cancel_before_hours >= 0),
  max_active_per_student  INT NOT NULL DEFAULT 2  CHECK (max_active_per_student >= 1),
  reminder_hours_before   INT NOT NULL DEFAULT 24 CHECK (reminder_hours_before >= 1),
  updated_by              UUID REFERENCES users(id),
  updated_at              TIMESTAMPTZ NOT NULL DEFAULT now()
);
INSERT INTO booking_policies (department) VALUES ('*') ON CONFLICT DO NOTHING;

-- department-specific row if present, otherwise the '*' default
CREATE OR REPLACE FUNCTION policy_for(p_dept TEXT)
RETURNS booking_policies LANGUAGE sql STABLE AS $$
  SELECT * FROM booking_policies
  WHERE department = p_dept OR department = '*'
  ORDER BY (department = '*')
  LIMIT 1
$$;

-- ---------- notifications : in-app inbox (email / LINE can be added as delivery channels later) ----------
CREATE TABLE notifications (
  id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id         UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  type            TEXT NOT NULL CHECK (type IN
                    ('booked', 'cancelled', 'reminder', 'task', 'task_due', 'summary', 'no_show', 'system')),
  title           TEXT NOT NULL,
  body            TEXT,
  appointment_id  UUID REFERENCES appointments(id) ON DELETE SET NULL,
  dedupe_key      TEXT,                       -- e.g. 'rem:<appointment id>' so scheduled jobs never send twice
  created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
  read_at         TIMESTAMPTZ,
  UNIQUE (user_id, dedupe_key)                -- NULL keys are allowed many times
);
CREATE INDEX idx_notif_user_unread ON notifications (user_id, created_at DESC) WHERE read_at IS NULL;
CREATE INDEX idx_notif_user ON notifications (user_id, created_at DESC);

-- ---------- book_slot v2 : enforces policy, then notifies both sides ----------
CREATE OR REPLACE FUNCTION book_slot(p_slot UUID, p_student UUID, p_topic TEXT)
RETURNS UUID LANGUAGE plpgsql AS $$
DECLARE
  v_advisor  UUID;
  v_start    TIMESTAMPTZ;
  v_dept     TEXT;
  v_pol      booking_policies;
  v_active   INT;
  v_appt     UUID;
  v_student  TEXT;
BEGIN
  SELECT s.advisor_id, s.starts_at, u.department
    INTO v_advisor, v_start, v_dept
  FROM availability_slots s
  JOIN users u ON u.id = s.advisor_id
  WHERE s.id = p_slot AND s.status = 'open'
  FOR UPDATE OF s;

  IF NOT FOUND THEN
    RAISE EXCEPTION 'slot_unavailable';
  END IF;

  v_pol := policy_for(v_dept);

  IF v_start < now() + make_interval(hours => v_pol.min_notice_hours) THEN
    RAISE EXCEPTION 'too_late_to_book';
  END IF;

  SELECT count(*) INTO v_active
  FROM appointments a
  JOIN availability_slots s2 ON s2.id = a.slot_id
  WHERE a.student_id = p_student
    AND a.status IN ('pending', 'confirmed')
    AND s2.starts_at > now();

  IF v_active >= v_pol.max_active_per_student THEN
    RAISE EXCEPTION 'too_many_active_appointments';
  END IF;

  INSERT INTO appointments (slot_id, advisor_id, student_id, topic)
  VALUES (p_slot, v_advisor, p_student, p_topic)
  RETURNING id INTO v_appt;

  UPDATE availability_slots SET status = 'booked' WHERE id = p_slot;

  SELECT full_name INTO v_student FROM users WHERE id = p_student;

  INSERT INTO notifications (user_id, type, title, body, appointment_id) VALUES
    (v_advisor, 'booked', v_student || ' จองนัดใหม่', p_topic, v_appt),
    (p_student, 'booked', 'จองนัดสำเร็จ',             p_topic, v_appt);

  RETURN v_appt;
END $$;

-- ---------- cancel_appointment : students are bound by the cancel deadline, advisors are not ----------
-- Usage: SELECT cancel_appointment(:appointment_id, :acting_user_id, :reason);
CREATE OR REPLACE FUNCTION cancel_appointment(p_appt UUID, p_by UUID, p_reason TEXT)
RETURNS VOID LANGUAGE plpgsql AS $$
DECLARE
  v_slot     UUID;
  v_start    TIMESTAMPTZ;
  v_student  UUID;
  v_advisor  UUID;
  v_dept     TEXT;
  v_role     TEXT;
  v_name     TEXT;
  v_pol      booking_policies;
BEGIN
  SELECT a.slot_id, s.starts_at, a.student_id, a.advisor_id, adv.department
    INTO v_slot, v_start, v_student, v_advisor, v_dept
  FROM appointments a
  JOIN availability_slots s ON s.id = a.slot_id
  JOIN users adv ON adv.id = a.advisor_id
  WHERE a.id = p_appt AND a.status IN ('pending', 'confirmed')
  FOR UPDATE OF a;

  IF NOT FOUND THEN
    RAISE EXCEPTION 'not_cancellable';
  END IF;

  SELECT role, full_name INTO v_role, v_name FROM users WHERE id = p_by;
  v_pol := policy_for(v_dept);

  IF v_role = 'student' AND v_start < now() + make_interval(hours => v_pol.cancel_before_hours) THEN
    RAISE EXCEPTION 'too_late_to_cancel';
  END IF;

  UPDATE appointments
  SET status = 'cancelled', cancel_reason = p_reason, cancelled_by = p_by, updated_at = now()
  WHERE id = p_appt;

  -- give the slot back so someone else can book it (only if it has not started yet)
  UPDATE availability_slots SET status = 'open' WHERE id = v_slot AND starts_at > now();

  INSERT INTO notifications (user_id, type, title, body, appointment_id)
  VALUES (
    CASE WHEN p_by = v_student THEN v_advisor ELSE v_student END,
    'cancelled', v_name || ' ยกเลิกนัด', p_reason, p_appt
  );
END $$;

-- ---------- send_reminders : run on a schedule (e.g. hourly); safe to run repeatedly ----------
-- Returns the number of NEW notifications created.
CREATE OR REPLACE FUNCTION send_reminders()
RETURNS INT LANGUAGE plpgsql AS $$
DECLARE
  v_new   INT := 0;
  v_count INT;
BEGIN
  -- 1) appointments starting within the department's reminder window, to both student and advisor
  INSERT INTO notifications (user_id, type, title, body, appointment_id, dedupe_key)
  SELECT t.uid, 'reminder', 'นัดหมายใกล้ถึงเวลา', a.topic, a.id, 'rem:' || a.id::text
  FROM appointments a
  JOIN availability_slots s ON s.id = a.slot_id
  JOIN users adv ON adv.id = a.advisor_id
  CROSS JOIN LATERAL policy_for(adv.department) p
  CROSS JOIN LATERAL (VALUES (a.student_id), (a.advisor_id)) AS t(uid)
  WHERE a.status IN ('pending', 'confirmed')
    AND s.starts_at > now()
    AND s.starts_at <= now() + make_interval(hours => p.reminder_hours_before)
  ON CONFLICT (user_id, dedupe_key) DO NOTHING;
  GET DIAGNOSTICS v_count = ROW_COUNT;
  v_new := v_new + v_count;

  -- 2) follow-up tasks past their due date, to the assignee
  INSERT INTO notifications (user_id, type, title, body, appointment_id, dedupe_key)
  SELECT tk.assignee_id, 'task_due', 'งานเลยกำหนด', tk.title, tk.appointment_id, 'due:' || tk.id::text
  FROM tasks tk
  WHERE tk.status IN ('todo', 'doing')
    AND tk.due_date IS NOT NULL
    AND tk.due_date < current_date
  ON CONFLICT (user_id, dedupe_key) DO NOTHING;
  GET DIAGNOSTICS v_count = ROW_COUNT;
  v_new := v_new + v_count;

  RETURN v_new;
END $$;

-- ---------- v_advisor_stats : feeds the department overview ----------
CREATE OR REPLACE VIEW v_advisor_stats AS
SELECT
  u.id          AS advisor_id,
  u.full_name,
  u.department,
  COALESCE(sl.slots_total, 0)   AS slots_total,      -- open + booked (cancelled excluded)
  COALESCE(sl.slots_booked, 0)  AS slots_booked,
  COALESCE(ap.completed, 0)     AS appts_completed,
  COALESCE(ap.no_show, 0)       AS appts_no_show,
  COALESCE(ap.cancelled, 0)     AS appts_cancelled,
  COALESCE(ap.upcoming, 0)      AS appts_upcoming
FROM users u
LEFT JOIN (
  SELECT advisor_id,
         count(*) FILTER (WHERE status IN ('open', 'booked')) AS slots_total,
         count(*) FILTER (WHERE status = 'booked')            AS slots_booked
  FROM availability_slots
  GROUP BY advisor_id
) sl ON sl.advisor_id = u.id
LEFT JOIN (
  SELECT a.advisor_id,
         count(*) FILTER (WHERE a.status = 'completed') AS completed,
         count(*) FILTER (WHERE a.status = 'no_show')   AS no_show,
         count(*) FILTER (WHERE a.status = 'cancelled') AS cancelled,
         count(*) FILTER (WHERE a.status IN ('pending', 'confirmed') AND s.starts_at > now()) AS upcoming
  FROM appointments a
  JOIN availability_slots s ON s.id = a.slot_id
  GROUP BY a.advisor_id
) ap ON ap.advisor_id = u.id
WHERE u.role = 'advisor';
