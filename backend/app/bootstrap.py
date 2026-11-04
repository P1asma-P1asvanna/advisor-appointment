"""Create the first admin on an empty database from BOOTSTRAP_ADMIN_* environment variables."""
import logging

from . import config
from .db import one
from .security import hash_password

log = logging.getLogger("advisor.bootstrap")


def ensure_admin(conn) -> bool:
    """Returns True when an admin was created. Does nothing when the variables are unset or any admin exists."""
    if not config.BOOTSTRAP_ADMIN_EMAIL:
        return False
    if one(conn, "SELECT 1 AS x FROM users WHERE role = 'admin' LIMIT 1"):
        return False
    created = one(
        conn,
        """INSERT INTO users (email, full_name, role, department, password_hash, must_change_password)
           VALUES (%(e)s, %(n)s, 'admin', NULL, %(h)s, true)
           ON CONFLICT (email) DO NOTHING RETURNING id""",
        {"e": config.BOOTSTRAP_ADMIN_EMAIL, "n": config.BOOTSTRAP_ADMIN_NAME, "h": hash_password(config.BOOTSTRAP_ADMIN_PASSWORD)},
    )
    if created is None:
        log.error("BOOTSTRAP_ADMIN_EMAIL %s already belongs to a non-admin account; no admin was created", config.BOOTSTRAP_ADMIN_EMAIL)
        return False
    log.warning("created the first admin %s; they must change the password at first sign-in", config.BOOTSTRAP_ADMIN_EMAIL)
    return True
