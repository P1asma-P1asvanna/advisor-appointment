"""One error shape for the whole API:  {"error": {"code": "...", "message": "...", "details": ...}}

`code` is stable and meant for the client to branch on; `message` is Thai text that can be shown
to the user as is.
"""
import logging
from typing import Any

log = logging.getLogger("advisor.api")


class ApiError(Exception):
    def __init__(self, status: int, code: str, message: str, details: Any = None, headers: dict | None = None):
        super().__init__(message)
        self.status = status
        self.code = code
        self.message = message
        self.details = details
        self.headers = headers


# Rules enforced inside the database functions (RAISE EXCEPTION '<code>') -> HTTP status + Thai message.
RULES: dict[str, tuple[int, str]] = {
    "slot_unavailable": (409, "ช่องเวลานี้ถูกจองไปแล้ว หรือไม่เปิดให้จอง"),
    "too_late_to_book": (409, "จองไม่ทัน ต้องจองล่วงหน้าตามกติกาของภาควิชา"),
    "too_many_active_appointments": (409, "คุณมีนัดที่รออยู่ครบตามกติกาแล้ว ยกเลิกหรือรอให้เสร็จก่อนจองเพิ่ม"),
    "student_time_conflict": (409, "คุณมีนัดอื่นที่ช่วงเวลาทับกับช่องนี้"),
    "too_late_to_cancel": (409, "ยกเลิกเองไม่ได้แล้วตามกติกาของภาควิชา กรุณาติดต่ออาจารย์โดยตรง"),
    "not_cancellable": (409, "นัดนี้ยกเลิกไม่ได้ เพราะไม่อยู่ในสถานะที่ยกเลิกได้"),
    "not_your_appointment": (403, "ไม่มีสิทธิ์จัดการนัดนี้"),
    "not_a_student": (403, "เฉพาะนักศึกษาเท่านั้นที่จองนัดได้"),
}


def map_db_error(exc: Any) -> ApiError | None:
    """Translate a psycopg error into an ApiError, or None if it is not one we expect."""
    sqlstate = getattr(exc, "sqlstate", None)
    diag = getattr(exc, "diag", None)
    message = getattr(diag, "message_primary", None) or str(exc)
    constraint = getattr(diag, "constraint_name", None)

    if sqlstate == "P0001" and message in RULES:
        status, text = RULES[message]
        return ApiError(status, message, text)
    if sqlstate == "23505":
        if constraint == "uq_active_appointment_per_slot":
            status, text = RULES["slot_unavailable"]
            return ApiError(status, "slot_unavailable", text)
        if constraint == "users_email_key":
            return ApiError(409, "email_taken", "อีเมลนี้ถูกใช้แล้ว")
        return ApiError(409, "already_exists", "มีข้อมูลนี้อยู่แล้ว")
    if sqlstate == "23P01":
        return ApiError(409, "slot_overlaps", "ช่วงเวลานี้ทับกับช่องที่เปิดไว้แล้ว")
    if sqlstate == "23503":
        return ApiError(422, "invalid_reference", "อ้างถึงข้อมูลที่ไม่มีอยู่")
    if sqlstate in ("23514", "22P02", "22007", "22008", "22003"):
        return ApiError(422, "invalid_value", "ค่าที่ส่งมาไม่ถูกต้อง")
    return None


def install_handlers(app: Any) -> None:
    import psycopg
    from fastapi.exceptions import RequestValidationError
    from fastapi.responses import JSONResponse

    def body(code: str, message: str, details: Any = None) -> dict:
        err: dict[str, Any] = {"code": code, "message": message}
        if details is not None:
            err["details"] = details
        return {"error": err}

    @app.exception_handler(ApiError)
    async def _api_error(request, exc: ApiError):
        return JSONResponse(status_code=exc.status, content=body(exc.code, exc.message, exc.details), headers=exc.headers)

    @app.exception_handler(RequestValidationError)
    async def _validation(request, exc: RequestValidationError):
        details = [{"loc": [str(p) for p in e.get("loc", [])], "message": e.get("msg", "")} for e in exc.errors()]
        return JSONResponse(status_code=422, content=body("validation_error", "ข้อมูลที่ส่งมาไม่ถูกต้อง", details))

    @app.exception_handler(psycopg.Error)
    async def _db_error(request, exc):
        mapped = map_db_error(exc)
        if mapped is not None:
            return JSONResponse(status_code=mapped.status, content=body(mapped.code, mapped.message))
        log.exception("unexpected database error", exc_info=exc)
        return JSONResponse(status_code=500, content=body("database_error", "ระบบฐานข้อมูลมีปัญหา กรุณาลองใหม่"))
