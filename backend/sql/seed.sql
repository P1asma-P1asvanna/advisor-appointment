-- Demo data. Dates are relative to today, so the demo never goes stale. Every account's password is: demo1234
-- Re-runnable: it clears all data first (including booking rules, which go back to the defaults).
SET timezone = 'Asia/Bangkok';

TRUNCATE notifications, tasks, advising_notes, appointments, availability_slots, login_attempts, users, booking_policies CASCADE;
INSERT INTO booking_policies (department) VALUES ('*');

-- ---------- users ----------
INSERT INTO users (id, email, full_name, role, department, password_hash) VALUES
 ('11111111-1111-1111-1111-000000000001', 'sureeporn@example.edu', 'อ.สุรีย์พร ใจดี',     'advisor', 'วิศวกรรมคอมพิวเตอร์', 'scrypt$16384$8$1$1VZjaDK1iUgUEmOULO7AhA==$HSATBasJg1lYqP7P22zbbFuOvwEwC4BDP0ptzNUebUA='),
 ('11111111-1111-1111-1111-000000000002', 'thana@example.edu',     'ธนา ศรีสุข',          'student', 'วิศวกรรมคอมพิวเตอร์', 'scrypt$16384$8$1$1VZjaDK1iUgUEmOULO7AhA==$HSATBasJg1lYqP7P22zbbFuOvwEwC4BDP0ptzNUebUA='),
 ('11111111-1111-1111-1111-000000000003', 'pimlada@example.edu',   'พิมพ์ลดา แก้วมณี',     'student', 'วิศวกรรมคอมพิวเตอร์', 'scrypt$16384$8$1$1VZjaDK1iUgUEmOULO7AhA==$HSATBasJg1lYqP7P22zbbFuOvwEwC4BDP0ptzNUebUA='),
 ('11111111-1111-1111-1111-000000000004', 'nattawut@example.edu',  'อ.ณัฐวุฒิ รัตนวงศ์',   'advisor', 'คณิตศาสตร์',            'scrypt$16384$8$1$1VZjaDK1iUgUEmOULO7AhA==$HSATBasJg1lYqP7P22zbbFuOvwEwC4BDP0ptzNUebUA='),
 ('11111111-1111-1111-1111-000000000005', 'mali@example.edu',      'มาลี วงศ์ประเสริฐ',    'admin',   'สำนักงานคณะ',          'scrypt$16384$8$1$1VZjaDK1iUgUEmOULO7AhA==$HSATBasJg1lYqP7P22zbbFuOvwEwC4BDP0ptzNUebUA=');

-- ---------- availability_slots  (A1 = อ.สุรีย์พร, A2 = อ.ณัฐวุฒิ) ----------
-- Bookable (open) slots are all 2+ days ahead, so booking tests never hit the 12 hour notice rule by accident.
INSERT INTO availability_slots (id, advisor_id, starts_at, ends_at, mode, location, meeting_url, status) VALUES
 -- A1, in the past
 ('22222222-2222-2222-2222-000000000001', '11111111-1111-1111-1111-000000000001', (current_date - 5 + time '13:00')::timestamptz, (current_date - 5 + time '13:30')::timestamptz, 'onsite', 'ห้อง 4-512 อาคารวิศวกรรม', NULL, 'booked'),
 ('22222222-2222-2222-2222-000000000002', '11111111-1111-1111-1111-000000000001', (current_date - 7 + time '14:00')::timestamptz, (current_date - 7 + time '14:30')::timestamptz, 'onsite', 'ห้อง 4-512 อาคารวิศวกรรม', NULL, 'booked'),
 ('22222222-2222-2222-2222-000000000003', '11111111-1111-1111-1111-000000000001', (current_date - 6 + time '09:00')::timestamptz, (current_date - 6 + time '09:30')::timestamptz, 'onsite', 'ห้อง 4-512 อาคารวิศวกรรม', NULL, 'booked'),
 ('22222222-2222-2222-2222-000000000004', '11111111-1111-1111-1111-000000000001', (current_date - 8 + time '11:00')::timestamptz, (current_date - 8 + time '11:30')::timestamptz, 'onsite', 'ห้อง 4-512 อาคารวิศวกรรม', NULL, 'open'),
 -- A1, upcoming
 ('22222222-2222-2222-2222-000000000005', '11111111-1111-1111-1111-000000000001', (current_date + 2 + time '09:00')::timestamptz, (current_date + 2 + time '09:30')::timestamptz, 'onsite', 'ห้อง 4-512 อาคารวิศวกรรม', NULL, 'booked'),
 ('22222222-2222-2222-2222-000000000006', '11111111-1111-1111-1111-000000000001', (current_date + 2 + time '09:30')::timestamptz, (current_date + 2 + time '10:00')::timestamptz, 'onsite', 'ห้อง 4-512 อาคารวิศวกรรม', NULL, 'open'),
 ('22222222-2222-2222-2222-000000000007', '11111111-1111-1111-1111-000000000001', (current_date + 3 + time '13:00')::timestamptz, (current_date + 3 + time '13:30')::timestamptz, 'online', 'ออนไลน์', 'https://meet.example.edu/sureeporn', 'open'),
 ('22222222-2222-2222-2222-000000000008', '11111111-1111-1111-1111-000000000001', (current_date + 3 + time '13:30')::timestamptz, (current_date + 3 + time '14:00')::timestamptz, 'onsite', 'ห้อง 4-512 อาคารวิศวกรรม', NULL, 'booked'),
 ('22222222-2222-2222-2222-000000000009', '11111111-1111-1111-1111-000000000001', (current_date + 4 + time '10:00')::timestamptz, (current_date + 4 + time '10:30')::timestamptz, 'onsite', 'ห้อง 4-512 อาคารวิศวกรรม', NULL, 'open'),
 ('22222222-2222-2222-2222-000000000010', '11111111-1111-1111-1111-000000000001', (current_date + 5 + time '14:00')::timestamptz, (current_date + 5 + time '14:30')::timestamptz, 'online', 'ออนไลน์', 'https://meet.example.edu/sureeporn', 'open'),
 ('22222222-2222-2222-2222-000000000011', '11111111-1111-1111-1111-000000000001', (current_date + 6 + time '11:00')::timestamptz, (current_date + 6 + time '11:30')::timestamptz, 'onsite', 'ห้อง 4-512 อาคารวิศวกรรม', NULL, 'cancelled'),
 -- A2
 ('22222222-2222-2222-2222-000000000012', '11111111-1111-1111-1111-000000000004', (current_date - 8 + time '15:00')::timestamptz, (current_date - 8 + time '15:30')::timestamptz, 'onsite', 'ห้อง 2-308 อาคารวิทยาศาสตร์', NULL, 'booked'),
 ('22222222-2222-2222-2222-000000000013', '11111111-1111-1111-1111-000000000004', (current_date - 2 + time '13:00')::timestamptz, (current_date - 2 + time '13:30')::timestamptz, 'onsite', 'ห้อง 2-308 อาคารวิทยาศาสตร์', NULL, 'booked'),
 ('22222222-2222-2222-2222-000000000014', '11111111-1111-1111-1111-000000000004', (current_date - 6 + time '10:00')::timestamptz, (current_date - 6 + time '10:30')::timestamptz, 'onsite', 'ห้อง 2-308 อาคารวิทยาศาสตร์', NULL, 'open'),
 ('22222222-2222-2222-2222-000000000015', '11111111-1111-1111-1111-000000000004', (current_date + 3 + time '11:00')::timestamptz, (current_date + 3 + time '11:30')::timestamptz, 'onsite', 'ห้อง 2-308 อาคารวิทยาศาสตร์', NULL, 'booked'),
 ('22222222-2222-2222-2222-000000000016', '11111111-1111-1111-1111-000000000004', (current_date + 3 + time '15:00')::timestamptz, (current_date + 3 + time '15:30')::timestamptz, 'onsite', 'ห้อง 2-308 อาคารวิทยาศาสตร์', NULL, 'open'),
 ('22222222-2222-2222-2222-000000000017', '11111111-1111-1111-1111-000000000004', (current_date + 5 + time '09:00')::timestamptz, (current_date + 5 + time '09:30')::timestamptz, 'online', 'ออนไลน์', 'https://meet.example.edu/nattawut', 'open');

-- ---------- appointments  (S1 = ธนา, S2 = พิมพ์ลดา) ----------
INSERT INTO appointments (id, slot_id, advisor_id, student_id, topic, status, cancel_reason, cancelled_by) VALUES
 ('33333333-3333-3333-3333-000000000001', '22222222-2222-2222-2222-000000000001', '11111111-1111-1111-1111-000000000001', '11111111-1111-1111-1111-000000000002', 'แผนการเรียนและการฝึกงาน',        'completed', NULL, NULL),
 ('33333333-3333-3333-3333-000000000002', '22222222-2222-2222-2222-000000000002', '11111111-1111-1111-1111-000000000001', '11111111-1111-1111-1111-000000000002', 'ตรวจแผนการเรียน',                'no_show',   NULL, NULL),
 ('33333333-3333-3333-3333-000000000003', '22222222-2222-2222-2222-000000000003', '11111111-1111-1111-1111-000000000001', '11111111-1111-1111-1111-000000000003', 'ปรึกษาเรื่องการลงทะเบียนเรียน',  'completed', NULL, NULL),
 ('33333333-3333-3333-3333-000000000004', '22222222-2222-2222-2222-000000000005', '11111111-1111-1111-1111-000000000001', '11111111-1111-1111-1111-000000000002', 'ปรึกษาเลือกวิชาเลือกเทอม 2',     'confirmed', NULL, NULL),
 ('33333333-3333-3333-3333-000000000005', '22222222-2222-2222-2222-000000000008', '11111111-1111-1111-1111-000000000001', '11111111-1111-1111-1111-000000000003', 'หัวข้อโครงงานจบ',                'confirmed', NULL, NULL),
 ('33333333-3333-3333-3333-000000000006', '22222222-2222-2222-2222-000000000012', '11111111-1111-1111-1111-000000000004', '11111111-1111-1111-1111-000000000003', 'ปรึกษาคะแนนสอบกลางภาค',         'completed', NULL, NULL),
 ('33333333-3333-3333-3333-000000000007', '22222222-2222-2222-2222-000000000013', '11111111-1111-1111-1111-000000000004', '11111111-1111-1111-1111-000000000002', 'ขอคำแนะนำวิชาเสริมคณิตศาสตร์',   'completed', NULL, NULL),
 ('33333333-3333-3333-3333-000000000008', '22222222-2222-2222-2222-000000000014', '11111111-1111-1111-1111-000000000004', '11111111-1111-1111-1111-000000000002', 'ทบทวนเนื้อหาก่อนสอบ',            'cancelled', 'ติดสอบวิชาอื่น', '11111111-1111-1111-1111-000000000002'),
 ('33333333-3333-3333-3333-000000000009', '22222222-2222-2222-2222-000000000015', '11111111-1111-1111-1111-000000000004', '11111111-1111-1111-1111-000000000003', 'เตรียมสอบวิชาแคลคูลัส 2',        'confirmed', NULL, NULL);

-- ---------- advising_notes ----------
INSERT INTO advising_notes (id, appointment_id, author_id, issues, summary, visibility) VALUES
 ('44444444-4444-4444-4444-000000000001', '33333333-3333-3333-3333-000000000001', '11111111-1111-1111-1111-000000000001',
  'ยังไม่แน่ใจเรื่องฝึกงานช่วงซัมเมอร์ และกังวลเรื่องเกรดวิชาโครงสร้างข้อมูล',
  'ตกลงให้ร่างแผนฝึกงาน 1 หน้า และเข้าติวกลุ่มวิชาโครงสร้างข้อมูลทุกวันพุธ', 'shared');

-- ---------- tasks ----------
INSERT INTO tasks (id, appointment_id, note_id, assignee_id, created_by, title, due_date, status, completed_at) VALUES
 ('55555555-5555-5555-5555-000000000001', '33333333-3333-3333-3333-000000000001', '44444444-4444-4444-4444-000000000001', '11111111-1111-1111-1111-000000000002', '11111111-1111-1111-1111-000000000001', 'ส่งร่างแผนฝึกงาน 1 หน้า',                 current_date + 5, 'doing', NULL),
 ('55555555-5555-5555-5555-000000000002', '33333333-3333-3333-3333-000000000001', '44444444-4444-4444-4444-000000000001', '11111111-1111-1111-1111-000000000002', '11111111-1111-1111-1111-000000000001', 'รวบรวมรายชื่อบริษัทที่รับฝึกงาน 5 แห่ง',   current_date - 2, 'todo',  NULL),
 ('55555555-5555-5555-5555-000000000003', '33333333-3333-3333-3333-000000000001', '44444444-4444-4444-4444-000000000001', '11111111-1111-1111-1111-000000000002', '11111111-1111-1111-1111-000000000001', 'ลงชื่อเข้าติววิชาโครงสร้างข้อมูล',          current_date - 3, 'done',  now() - interval '3 days');

-- ---------- notifications ----------
INSERT INTO notifications (user_id, type, title, body, appointment_id, dedupe_key, created_at, read_at) VALUES
 ('11111111-1111-1111-1111-000000000001', 'booked',   'ธนา ศรีสุข จองนัดใหม่',      'ปรึกษาเลือกวิชาเลือกเทอม 2',                 '33333333-3333-3333-3333-000000000004', NULL, now() - interval '1 day',  NULL),
 ('11111111-1111-1111-1111-000000000002', 'task_due', 'งานเลยกำหนด',                'รวบรวมรายชื่อบริษัทที่รับฝึกงาน 5 แห่ง',     '33333333-3333-3333-3333-000000000001', 'due:55555555-5555-5555-5555-000000000002', now() - interval '2 hours', NULL),
 ('11111111-1111-1111-1111-000000000002', 'summary',  'อาจารย์บันทึกสรุปนัดแล้ว',   'แผนการเรียนและการฝึกงาน',                    '33333333-3333-3333-3333-000000000001', 'sum:33333333-3333-3333-3333-000000000001', now() - interval '5 days', now() - interval '4 days');
