-- Removes ALL demo data: users, slots, appointments, notes, tasks, notifications and login attempts.
-- The schema stays, and the booking rules go back to the defaults.
-- Run it once in the Neon SQL Editor before real users start, then create the first admin by setting
-- BOOTSTRAP_ADMIN_EMAIL / BOOTSTRAP_ADMIN_PASSWORD on the API (see README) and restarting it.

TRUNCATE notifications, tasks, advising_notes, appointments, availability_slots,
         login_attempts, booking_policies, users CASCADE;
INSERT INTO booking_policies (department) VALUES ('*');
