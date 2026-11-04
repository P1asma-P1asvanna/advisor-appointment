"""Authentication and role checks, used as FastAPI dependencies."""
from uuid import UUID

import jwt
from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from .db import get_conn, one
from .errors import ApiError
from .security import decode_token

bearer = HTTPBearer(auto_error=False)

_UNAUTH_HEADERS = {"WWW-Authenticate": "Bearer"}


def public_user(row: dict) -> dict:
    return {
        "id": row["id"],
        "email": row["email"],
        "full_name": row["full_name"],
        "role": row["role"],
        "department": row["department"],
        "must_change_password": row["must_change_password"],
    }


def _load_user(creds: HTTPAuthorizationCredentials | None, conn) -> dict:
    if creds is None:
        raise ApiError(401, "not_authenticated", "กรุณาเข้าสู่ระบบ", headers=_UNAUTH_HEADERS)
    try:
        claims = decode_token(creds.credentials)
        user_id = UUID(claims["sub"])
        issued_at = float(claims.get("iat", 0))
    except (jwt.PyJWTError, ValueError, KeyError, TypeError):
        raise ApiError(401, "invalid_token", "เซสชันหมดอายุหรือไม่ถูกต้อง กรุณาเข้าสู่ระบบใหม่", headers=_UNAUTH_HEADERS)
    row = one(
        conn,
        """SELECT id, email, full_name, role, department, is_active, must_change_password, password_changed_at
           FROM users WHERE id = %(id)s""",
        {"id": user_id},
    )
    if row is None or not row["is_active"]:
        raise ApiError(401, "invalid_token", "บัญชีนี้ใช้งานไม่ได้แล้ว กรุณาติดต่อเจ้าหน้าที่", headers=_UNAUTH_HEADERS)
    changed = row["password_changed_at"]
    if changed is not None and issued_at < changed.timestamp():
        # the password was changed or reset after this token was issued
        raise ApiError(401, "invalid_token", "รหัสผ่านถูกเปลี่ยนแล้ว กรุณาเข้าสู่ระบบใหม่", headers=_UNAUTH_HEADERS)
    return row


def current_user_even_if_password_unchanged(
    creds: HTTPAuthorizationCredentials | None = Depends(bearer),
    conn=Depends(get_conn),
) -> dict:
    """Used only by /me and /auth/change-password, the two things a user who must pick a new password can do."""
    return _load_user(creds, conn)


def current_user(
    creds: HTTPAuthorizationCredentials | None = Depends(bearer),
    conn=Depends(get_conn),
) -> dict:
    user = _load_user(creds, conn)
    if user["must_change_password"]:
        raise ApiError(403, "password_change_required", "กรุณาตั้งรหัสผ่านใหม่ก่อนใช้งานต่อ")
    return user


def require_roles(*roles: str):
    def check(user: dict = Depends(current_user)) -> dict:
        if user["role"] not in roles:
            raise ApiError(403, "forbidden", "บทบาทของคุณไม่มีสิทธิ์ทำรายการนี้")
        return user

    return check
