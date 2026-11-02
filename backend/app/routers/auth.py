from fastapi import APIRouter, Depends

from .. import config
from ..db import get_conn, many, one
from ..deps import current_user, public_user
from ..errors import ApiError
from ..schemas import LoginIn
from ..security import DUMMY_HASH, create_token, verify_password

router = APIRouter(tags=["auth"])

ROLE_TH = {"student": "นักศึกษา", "advisor": "อาจารย์", "admin": "เจ้าหน้าที่ภาควิชา"}


@router.post("/auth/login")
def login(body: LoginIn, conn=Depends(get_conn)):
    row = one(
        conn,
        "SELECT id, email, full_name, role, department, password_hash FROM users WHERE lower(email) = %(email)s",
        {"email": body.email},
    )
    stored = row["password_hash"] if row and row["password_hash"] else None
    ok = verify_password(body.password, stored or DUMMY_HASH)
    if row is None or stored is None or not ok:
        raise ApiError(401, "invalid_credentials", "อีเมลหรือรหัสผ่านไม่ถูกต้อง")
    if body.role is not None and body.role != row["role"]:
        raise ApiError(
            403,
            "role_mismatch",
            f"บัญชีนี้เป็นของ{ROLE_TH[row['role']]} กรุณาเลือกบทบาทให้ตรงกัน",
        )
    return {
        "access_token": create_token(row["id"], row["role"]),
        "token_type": "bearer",
        "expires_in": config.JWT_TTL_MINUTES * 60,
        "user": public_user(row),
    }


@router.get("/me")
def me(user=Depends(current_user)):
    return public_user(user)


@router.get("/advisors")
def advisors(department: str | None = None, user=Depends(current_user), conn=Depends(get_conn)):
    """Advisors a student can pick from, optionally for one department."""
    rows = many(
        conn,
        """
        SELECT id, full_name AS name, department FROM users
        WHERE role = 'advisor' AND (%(department)s::text IS NULL OR department = %(department)s::text)
        ORDER BY department, full_name
        """,
        {"department": department},
    )
    return {"items": rows}
