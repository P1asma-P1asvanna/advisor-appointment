-- Advisor Appointment — schema v4 (additive migration; apply after schema.sql, schema_v2.sql, schema_v3.sql)
-- 1) users.is_active            : an admin can switch an account off without deleting its history
-- 2) users.must_change_password : set when an admin creates the account or resets its password
-- 3) users.password_changed_at  : tokens issued before this moment stop working
-- 4) login_attempts             : failed sign-ins, used to lock an email for a while after too many

ALTER TABLE users ADD COLUMN IF NOT EXISTS is_active BOOLEAN NOT NULL DEFAULT true;
ALTER TABLE users ADD COLUMN IF NOT EXISTS must_change_password BOOLEAN NOT NULL DEFAULT false;
ALTER TABLE users ADD COLUMN IF NOT EXISTS password_changed_at TIMESTAMPTZ;

CREATE TABLE IF NOT EXISTS login_attempts (
  id           BIGSERIAL PRIMARY KEY,
  email        TEXT NOT NULL,
  attempted_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS ix_login_attempts_email_time ON login_attempts (email, attempted_at);
