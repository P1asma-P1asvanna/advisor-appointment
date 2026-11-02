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


def validate() -> None:
    if len(JWT_SECRET) < 32:
        raise RuntimeError(
            "JWT_SECRET must be set to a random string of at least 32 characters "
            "(or run with APP_ENV=dev for local development)."
        )
