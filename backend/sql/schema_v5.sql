-- v5: reset-password-by-email tokens and the admin audit log. Safe to run more than once.

-- One row per emailed reset link. Only a SHA-256 of the token is stored, so a database leak cannot be used to reset anyone.
CREATE TABLE IF NOT EXISTS password_resets (
  id          BIGSERIAL PRIMARY KEY,
  user_id     UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  token_hash  TEXT NOT NULL UNIQUE,
  expires_at  TIMESTAMPTZ NOT NULL,
  used_at     TIMESTAMPTZ,
  created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_password_resets_user ON password_resets (user_id, created_at DESC);

-- Who changed what. Emails are copied in, so the trail stays readable even for accounts that change later.
-- No foreign keys on purpose: history must outlive the rows it talks about. Never put passwords or tokens in details.
CREATE TABLE IF NOT EXISTS audit_log (
  id            BIGSERIAL PRIMARY KEY,
  at            TIMESTAMPTZ NOT NULL DEFAULT now(),
  actor_id      UUID,
  actor_email   TEXT,
  action        TEXT NOT NULL,
  target_id     UUID,
  target_email  TEXT,
  details       TEXT
);
CREATE INDEX IF NOT EXISTS idx_audit_at ON audit_log (at DESC);
