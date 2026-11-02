-- Advisor Appointment — schema v3 (additive migration; apply after schema.sql and schema_v2.sql)
-- 1) users.password_hash for API login
-- 2) book_slot(): serialises per student (closes a race on the active-appointment limit),
--    checks the caller is a student, and refuses overlapping appointments for the same student
-- 3) cancel_appointment(): only the student or advisor of the appointment may cancel it

ALTER TABLE users ADD COLUMN IF NOT EXISTS password_hash TEXT;

-- ---------- book_slot v3 ----------
CREATE OR REPLACE FUNCTION book_slot(p_slot UUID, p_student UUID, p_topic TEXT)
RETURNS UUID LANGUAGE plpgsql AS $$
DECLARE
  v_advisor  UUID;
  v_start    TIMESTAMPTZ;
  v_end      TIMESTAMPTZ;
  v_dept     TEXT;
  v_pol      booking_policies;
  v_active   INT;
  v_appt     UUID;
  v_student  TEXT;
BEGIN
  SELECT full_name INTO v_student FROM users WHERE id = p_student AND role = 'student';
  IF NOT FOUND THEN
    RAISE EXCEPTION 'not_a_student';
  END IF;

  -- Two concurrent bookings by the same student would both count the same number of active
  -- appointments and could exceed the limit. This lock makes them queue (released at commit).
  PERFORM pg_advisory_xact_lock(hashtextextended(p_student::text, 0));

  SELECT s.advisor_id, s.starts_at, s.ends_at, u.department
    INTO v_advisor, v_start, v_end, v_dept
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

  IF EXISTS (
    SELECT 1
    FROM appointments a
    JOIN availability_slots s3 ON s3.id = a.slot_id
    WHERE a.student_id = p_student
      AND a.status IN ('pending', 'confirmed')
      AND tstzrange(s3.starts_at, s3.ends_at) && tstzrange(v_start, v_end)
  ) THEN
    RAISE EXCEPTION 'student_time_conflict';
  END IF;

  INSERT INTO appointments (slot_id, advisor_id, student_id, topic)
  VALUES (p_slot, v_advisor, p_student, p_topic)
  RETURNING id INTO v_appt;

  UPDATE availability_slots SET status = 'booked' WHERE id = p_slot;

  INSERT INTO notifications (user_id, type, title, body, appointment_id) VALUES
    (v_advisor, 'booked', v_student || ' จองนัดใหม่', p_topic, v_appt),
    (p_student, 'booked', 'จองนัดสำเร็จ',             p_topic, v_appt);

  RETURN v_appt;
END $$;

-- ---------- cancel_appointment v3 ----------
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

  IF p_by IS DISTINCT FROM v_student AND p_by IS DISTINCT FROM v_advisor THEN
    RAISE EXCEPTION 'not_your_appointment';
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
