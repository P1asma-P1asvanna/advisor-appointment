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
    }


def current_user(
    creds: HTTPAuthorizationCredentials | None = Depends(bearer),
    conn=Depends(get_conn),
) -> dict:
    if creds is None:
        raise ApiError(401, "not_authenticated", "กรุณาเข้าสู่ระบบ", headers=_UNAUTH_HEADERS)
    try:
        claims = decode_token(creds.credentials)
        user_id = UUID(claims["sub"])
    except (jwt.PyJWTError, ValueError, KeyError):
        raise ApiError(401, "invalid_token", "เซสชันหมดอายุหรือไม่ถูกต้อง กรุณาเข้าสู่ระบบใหม่", headers=_UNAUTH_HEADERS)
    row = one(
        conn,
        "SELECT id, email, full_name, role, department FROM users WHERE id = %(id)s",
        {"id": user_id},
    )
    if row is None:
        raise ApiError(401, "invalid_token", "ไม่พบบัญชีผู้ใช้นี้แล้ว", headers=_UNAUTH_HEADERS)
    return row


def require_roles(*roles: str):
    def check(user: dict = Depends(current_user)) -> dict:
        if user["role"] not in roles:
            raise ApiError(403, "forbidden", "บทบาทของคุณไม่มีสิทธิ์ทำรายการนี้")
        return user

    return check
