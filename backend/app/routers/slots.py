from datetime import date, datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends

from ..db import get_conn, many, one
from ..deps import current_user, require_roles
from ..errors import ApiError
from ..repo import SLOT_SELECT, shape_slot
from ..notify import fmt_when, notify
from ..schemas import SlotIn, SlotPatch

router = APIRouter(prefix="/slots", tags=["slots"])

STATUSES = ("open", "booked", "cancelled")


@router.get("")
def list_slots(
    advisor_id: UUID | None = None,
    department: str | None = None,
    status: str | None = None,
    from_date: date | None = None,
    to_date: date | None = None,
    limit: int = 200,
    user=Depends(current_user),
    conn=Depends(get_conn),
):
    """Availability slots.

    * student: only open slots in the future (what can be booked)
    * advisor: only their own slots, any status
    * admin:   any slot
    `from_date` / `to_date` are inclusive calendar dates in the database time zone.
    """
    if status is not None and status not in STATUSES:
        raise ApiError(422, "invalid_status", "สถานะต้องเป็น open, booked หรือ cancelled")
    only_future = False
    if user["role"] == "advisor":
        advisor_id = user["id"]
    elif user["role"] == "student":
        status = "open"
        only_future = True
    rows = many(
        conn,
        SLOT_SELECT
        + """
        WHERE (%(advisor_id)s::uuid IS NULL OR s.advisor_id = %(advisor_id)s::uuid)
          AND (%(department)s::text IS NULL OR u.department = %(department)s::text)
          AND (%(status)s::text IS NULL OR s.status = %(status)s::text)
          AND (%(from_date)s::date IS NULL OR s.starts_at >= %(from_date)s::date)
          AND (%(to_date)s::date IS NULL OR s.starts_at < (%(to_date)s::date + 1))
          AND (NOT %(only_future)s::bool OR s.starts_at > now())
        ORDER BY s.starts_at
        LIMIT %(limit)s
        """,
        {
            "advisor_id": advisor_id,
            "department": department,
            "status": status,
            "from_date": from_date,
            "to_date": to_date,
            "only_future": only_future,
            "limit": max(1, min(limit, 500)),
        },
    )
    show_student = user["role"] != "student"
    return {"items": [shape_slot(r, show_student=show_student) for r in rows]}


@router.post("", status_code=201)
def create_slot(body: SlotIn, user=Depends(require_roles("advisor")), conn=Depends(get_conn)):
    """Open a time window for students. Overlapping an existing slot gives 409 slot_overlaps."""
    if body.starts_at <= datetime.now(timezone.utc):
        raise ApiError(422, "slot_in_past", "เลือกเวลาในอนาคต")
    created = one(
        conn,
        """
        INSERT INTO availability_slots (advisor_id, starts_at, ends_at, mode, location, meeting_url)
        VALUES (%(advisor_id)s, %(starts_at)s, %(ends_at)s, %(mode)s, %(location)s, %(meeting_url)s)
        RETURNING id
        """,
        {
            "advisor_id": user["id"],
            "starts_at": body.starts_at,
            "ends_at": body.ends_at,
            "mode": body.mode,
            "location": body.location,
            "meeting_url": body.meeting_url,
        },
    )
    row = one(conn, SLOT_SELECT + " WHERE s.id = %(id)s", {"id": created["id"]})
    return shape_slot(row, show_student=True)


@router.post("/{slot_id}/cancel")
def cancel_slot(slot_id: UUID, user=Depends(require_roles("advisor")), conn=Depends(get_conn)):
    """Close a slot that is still open. A booked slot is freed by cancelling its appointment instead."""
    changed = one(
        conn,
        """
        UPDATE availability_slots SET status = 'cancelled'
        WHERE id = %(id)s AND advisor_id = %(uid)s AND status = 'open'
        RETURNING id
        """,
        {"id": slot_id, "uid": user["id"]},
    )
    if changed is None:
        exists = one(
            conn,
            "SELECT 1 AS x FROM availability_slots WHERE id = %(id)s AND advisor_id = %(uid)s",
            {"id": slot_id, "uid": user["id"]},
        )
        if exists is None:
            raise ApiError(404, "slot_not_found", "ไม่พบช่องเวลานี้")
        raise ApiError(409, "slot_not_open", "ปิดได้เฉพาะช่องที่ยังว่าง ถ้ามีคนจองแล้วให้ยกเลิกนัดแทน")
    row = one(conn, SLOT_SELECT + " WHERE s.id = %(id)s", {"id": slot_id})
    return shape_slot(row, show_student=True)


@router.patch("/{slot_id}")
def update_slot(slot_id: UUID, body: SlotPatch, user=Depends(require_roles("advisor")), conn=Depends(get_conn)):
    """Fix a slot you opened. An open slot can change time, mode and place; a booked slot can change only
    the mode and place (its student is told), because moving the time would break their plans."""
    slot = one(conn, SLOT_SELECT + " WHERE s.id = %(id)s AND s.advisor_id = %(uid)s", {"id": slot_id, "uid": user["id"]})
    if slot is None:
        raise ApiError(404, "slot_not_found", "ไม่พบช่องเวลานี้")
    if slot["status"] == "cancelled":
        raise ApiError(409, "slot_closed", "ช่องนี้ถูกปิดไปแล้ว แก้ไขไม่ได้ ให้เปิดช่องใหม่แทน")
    now = datetime.now(timezone.utc)
    if slot["starts_at"] <= now:
        raise ApiError(409, "slot_started", "ช่องเวลานี้เริ่มหรือผ่านไปแล้ว แก้ไขไม่ได้")
    starts, ends = slot["starts_at"], slot["ends_at"]
    if body.starts_at is not None:
        if slot["status"] != "open":
            raise ApiError(409, "slot_booked_time", "ช่องที่มีคนจองแล้วเปลี่ยนเวลาไม่ได้ ให้ยกเลิกนัดแล้วเปิดช่องใหม่")
        if body.starts_at <= now:
            raise ApiError(422, "slot_in_past", "เลือกเวลาในอนาคต")
        starts, ends = body.starts_at, body.ends_at
    fields = body.model_fields_set
    mode = body.mode or slot["mode"]
    location = (body.location or None) if "location" in fields else slot["location"]
    url = (body.meeting_url or None) if "meeting_url" in fields else slot["meeting_url"]
    where_changed = (mode, location, url) != (slot["mode"], slot["location"], slot["meeting_url"])
    with conn.transaction():
        one(
            conn,
            """
            UPDATE availability_slots SET starts_at = %(s)s, ends_at = %(e)s, mode = %(m)s, location = %(l)s, meeting_url = %(u)s
            WHERE id = %(id)s RETURNING id
            """,
            {"s": starts, "e": ends, "m": mode, "l": location, "u": url, "id": slot_id},
        )
        if slot["status"] == "booked" and where_changed:
            appt = one(
                conn,
                "SELECT id, student_id, topic FROM appointments WHERE slot_id = %(id)s AND status IN ('pending', 'confirmed')",
                {"id": slot_id},
            )
            if appt:
                notify(conn, appt["student_id"], "system", "อาจารย์แก้ไขสถานที่/ลิงก์นัด",
                       f"{fmt_when(starts)} · {appt['topic']}", appt["id"])
    return shape_slot(one(conn, SLOT_SELECT + " WHERE s.id = %(id)s", {"id": slot_id}), show_student=True)
