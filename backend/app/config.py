"""Settings, read from environment variables."""
import os

# "dev" allows a built-in JWT secret so a laptop works with zero setup. Anything else
# (the default) refuses to start without JWT_SECRET, so a forgotten variable can never
# silently run production with a known secret.
APP_ENV = os.environ.get("APP_ENV", "prod")

DATABASE_URL = os.environ.get("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/advisor")
DB_TIMEZONE = os.environ.get("DB_TIMEZONE", "Asia/Bangkok")
DB_POOL_MAX = int(os.environ.get("DB_POOL_MAX", "10"))

JWT_SECRET = os.environ.get("JWT_SECRET") or (
    "dev-only-secret-change-me-0123456789abcdef" if APP_ENV == "dev" else ""
)
JWT_ALGORITHM = "HS256"
JWT_TTL_MINUTES = int(os.environ.get("JWT_TTL_MINUTES", "480"))

# Comma separated list, e.g. "https://app.example.edu,http://localhost:5173"
CORS_ORIGINS = [o.strip() for o in os.environ.get("CORS_ORIGINS", "").split(",") if o.strip()]


# Failed sign-ins allowed per email inside the window before the email is locked for the rest of it.
LOGIN_MAX_FAILURES = int(os.environ.get("LOGIN_MAX_FAILURES", "5"))
LOGIN_WINDOW_MINUTES = int(os.environ.get("LOGIN_WINDOW_MINUTES", "15"))

# First admin for an empty database. Created at start-up only when no admin exists yet, and must change
# the password on first sign-in. Remove BOOTSTRAP_ADMIN_PASSWORD from the environment afterwards.
BOOTSTRAP_ADMIN_EMAIL = os.environ.get("BOOTSTRAP_ADMIN_EMAIL", "").strip().lower()
BOOTSTRAP_ADMIN_PASSWORD = os.environ.get("BOOTSTRAP_ADMIN_PASSWORD", "")
BOOTSTRAP_ADMIN_NAME = os.environ.get("BOOTSTRAP_ADMIN_NAME", "ผู้ดูแลระบบ").strip() or "ผู้ดูแลระบบ"


def validate() -> None:
    if len(JWT_SECRET) < 32:
        raise RuntimeError(
            "JWT_SECRET must be set to a random string of at least 32 characters "
            "(or run with APP_ENV=dev for local development)."
        )
    if BOOTSTRAP_ADMIN_EMAIL and len(BOOTSTRAP_ADMIN_PASSWORD) < 8:
        raise RuntimeError("BOOTSTRAP_ADMIN_PASSWORD must be at least 8 characters.")
