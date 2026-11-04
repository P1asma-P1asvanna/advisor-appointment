"""Lock an email for a while after too many failed sign-ins.

Failures are stored in the database (table login_attempts), so the lock survives a restart and works
when several API instances run. Unknown emails are counted too, so the response never reveals whether
an account exists. The lock is per email, not per address: it stops password guessing from anywhere,
at the price that someone can keep a known email locked out for a few minutes.
"""
import math
from typing import Any

from . import config
from .db import one, run
from .errors import ApiError


def ensure_not_locked(conn: Any, email: str) -> None:
    row = one(
        conn,
        """
        SELECT count(*) AS n, min(attempted_at) AS first_at,
               extract(epoch FROM (min(attempted_at) + make_interval(mins => %(win)s) - now())) AS wait_s
        FROM login_attempts
        WHERE email = %(email)s AND attempted_at > now() - make_interval(mins => %(win)s)
        """,
        {"email": email, "win": config.LOGIN_WINDOW_MINUTES},
    )
    if row and row["n"] >= config.LOGIN_MAX_FAILURES:
        minutes = max(1, math.ceil(float(row["wait_s"] or 0) / 60))
        raise ApiError(
            429,
            "too_many_attempts",
            f"ลองเข้าสู่ระบบผิดหลายครั้งเกินไป กรุณารอประมาณ {minutes} นาทีแล้วลองใหม่",
            details={"retry_after_minutes": minutes},
            headers={"Retry-After": str(minutes * 60)},
        )


def record_failure(conn: Any, email: str) -> None:
    run(conn, "INSERT INTO login_attempts (email) VALUES (%(email)s)", {"email": email})
    run(conn, "DELETE FROM login_attempts WHERE attempted_at < now() - interval '1 day'")


def clear(conn: Any, email: str) -> None:
    run(conn, "DELETE FROM login_attempts WHERE email = %(email)s", {"email": email})
