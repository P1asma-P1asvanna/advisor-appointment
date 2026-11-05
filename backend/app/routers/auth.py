import hashlib
import secrets
from datetime import datetime, timezone

from fastapi import APIRouter, Depends

from .. import audit, config, mailer, throttle
from ..db import get_conn, many, one, run
from ..deps import current_user, current_user_even_if_password_unchanged, public_user
from ..errors import ApiError
from ..schemas import ChangePasswordIn, ForgotIn, LoginIn, ProfilePatch, ResetIn
from ..security import DUMMY_HASH, create_token, hash_password, verify_password

router = APIRouter(tags=["auth"])

ROLE_TH = {"student": "นักศึกษา", "advisor": "อาจารย์", "admin": "เจ้าหน้าที่ภาควิชา"}


def _session(row: dict) -> dict:
    return {
        "access_token": create_token(row["id"], row["role"]),
        "token_type": "bearer",
        "expires_in": config.JWT_TTL_MINUTES * 60,
        "user": public_user(row),
    }


@router.post("/auth/login")
def login(body: LoginIn, conn=Depends(get_conn)):
    throttle.ensure_not_locked(conn, body.email)
    row = one(
        conn,
        """SELECT id, email, full_name, role, department, password_hash, is_active, must_change_password
           FROM users WHERE lower(email) = %(email)s""",
        {"email": body.email},
    )
    stored = row["password_hash"] if row and row["password_hash"] else None
    ok = verify_password(body.password, stored or DUMMY_HASH)
    if row is None or stored is None or not ok:
        throttle.record_failure(conn, body.email)
        raise ApiError(401, "invalid_credentials", "อีเมลหรือรหัสผ่านไม่ถูกต้อง")
    if not row["is_active"]:
        raise ApiError(403, "account_disabled", "บัญชีนี้ถูกปิดการใช้งาน กรุณาติดต่อเจ้าหน้าที่ภาควิชา")
    if body.role is not None and body.role != row["role"]:
        raise ApiError(
            403,
            "role_mismatch",
            f"บัญชีนี้เป็นของ{ROLE_TH[row['role']]} กรุณาเลือกบทบาทให้ตรงกัน",
        )
    throttle.clear(conn, body.email)
    return _session(row)


@router.post("/auth/change-password")
def change_password(
    body: ChangePasswordIn,
    user=Depends(current_user_even_if_password_unchanged),
    conn=Depends(get_conn),
):
    """Change my own password. Every older sign-in stops working, so the response carries a fresh token."""
    throttle.ensure_not_locked(conn, user["email"])
    stored = one(conn, "SELECT password_hash FROM users WHERE id = %(id)s", {"id": user["id"]})["password_hash"]
    if not stored or not verify_password(body.current_password, stored):
        throttle.record_failure(conn, user["email"])
        raise ApiError(403, "wrong_password", "รหัสผ่านปัจจุบันไม่ถูกต้อง")
    now = datetime.now(timezone.utc)
    row = one(
        conn,
        """UPDATE users SET password_hash = %(h)s, must_change_password = false, password_changed_at = %(now)s
           WHERE id = %(id)s
           RETURNING id, email, full_name, role, department, must_change_password""",
        {"h": hash_password(body.new_password), "now": now, "id": user["id"]},
    )
    throttle.clear(conn, user["email"])
    return _session(row)


@router.get("/auth/features")
def features():
    """What the sign-in page may offer. Reset by email exists only when mail is configured."""
    return {"password_reset": mailer.enabled()}


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


@router.post("/auth/forgot-password")
def forgot_password(body: ForgotIn, conn=Depends(get_conn)):
    """Email a single-use reset link. The answer is always the same, so nobody can use this to find out
    which emails have accounts. At most RESET_MAX_PER_HOUR links per account per hour."""
    generic = {"ok": True}
    if not mailer.enabled():
        return generic
    u = one(conn, "SELECT id, email, full_name FROM users WHERE email = %(e)s AND is_active", {"e": body.email})
    if u is None:
        return generic
    recent = one(
        conn,
        "SELECT count(*) AS n FROM password_resets WHERE user_id = %(id)s AND created_at > now() - interval '1 hour'",
        {"id": u["id"]},
    )
    if recent["n"] >= config.RESET_MAX_PER_HOUR:
        return generic
    token = secrets.token_urlsafe(32)
    with conn.transaction():
        run(conn, "UPDATE password_resets SET used_at = now() WHERE user_id = %(id)s AND used_at IS NULL", {"id": u["id"]})
        run(
            conn,
            """INSERT INTO password_resets (user_id, token_hash, expires_at)
               VALUES (%(id)s, %(h)s, now() + make_interval(mins => %(m)s))""",
            {"id": u["id"], "h": _hash_token(token), "m": config.RESET_TOKEN_MINUTES},
        )
    mailer.send_reset_link(u, token)
    return generic


@router.post("/auth/reset-password")
def reset_password(body: ResetIn, conn=Depends(get_conn)):
    """Set a new password with the emailed token. Signs the person out everywhere and uses up every link."""
    row = one(
        conn,
        """SELECT r.user_id AS id, u.email FROM password_resets r JOIN users u ON u.id = r.user_id
           WHERE r.token_hash = %(h)s AND r.used_at IS NULL AND r.expires_at > now() AND u.is_active""",
        {"h": _hash_token(body.token)},
    )
    if row is None:
        raise ApiError(400, "invalid_or_expired_token", "ลิงก์นี้ใช้ไม่ได้หรือหมดอายุแล้ว กรุณาขอลิงก์ใหม่")
    with conn.transaction():
        run(
            conn,
            """UPDATE users SET password_hash = %(h)s, must_change_password = false, password_changed_at = %(now)s
               WHERE id = %(id)s""",
            {"h": hash_password(body.new_password), "now": datetime.now(timezone.utc), "id": row["id"]},
        )
        run(conn, "UPDATE password_resets SET used_at = now() WHERE user_id = %(id)s AND used_at IS NULL", {"id": row["id"]})
        throttle.clear(conn, row["email"])
        audit.log(conn, None, "user.password_reset_by_email", row)
    return {"ok": True}


@router.get("/me")
def me(user=Depends(current_user_even_if_password_unchanged)):
    return public_user(user)


@router.patch("/me")
def update_me(body: ProfilePatch, user=Depends(current_user), conn=Depends(get_conn)):
    """Anyone may fix their own display name. Email, role and department are changed by the admin."""
    row = one(
        conn,
        """UPDATE users SET full_name = %(n)s WHERE id = %(id)s
           RETURNING id, email, full_name, role, department, must_change_password""",
        {"n": body.full_name, "id": user["id"]},
    )
    return public_user(row)


@router.get("/advisors")
def advisors(department: str | None = None, user=Depends(current_user), conn=Depends(get_conn)):
    """Advisors a student can pick from, optionally for one department."""
    rows = many(
        conn,
        """
        SELECT id, full_name AS name, department FROM users
        WHERE role = 'advisor' AND is_active AND (%(department)s::text IS NULL OR department = %(department)s::text)
        ORDER BY department, full_name
        """,
        {"department": department},
    )
    return {"items": rows}
