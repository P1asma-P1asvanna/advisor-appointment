"""Shared SELECTs and the JSON shapes returned to clients."""
from typing import Any
from uuid import UUID

from .db import one
from .errors import ApiError

APPT_SELECT = """
SELECT a.id, a.status, a.topic, a.cancel_reason, a.created_at, a.updated_at,
       a.slot_id, s.starts_at, s.ends_at, s.mode, s.location, s.meeting_url,
       a.advisor_id, adv.full_name AS advisor_name, adv.department,
       a.student_id, stu.full_name AS student_name
FROM appointments a
JOIN availability_slots s ON s.id = a.slot_id
JOIN users adv ON adv.id = a.advisor_id
JOIN users stu ON stu.id = a.student_id
"""

SLOT_SELECT = """
SELECT s.id, s.advisor_id, u.full_name AS advisor_name, u.department,
       s.starts_at, s.ends_at, s.mode, s.location, s.meeting_url, s.status,
       a.id AS appointment_id, st.full_name AS student_name
FROM availability_slots s
JOIN users u ON u.id = s.advisor_id
LEFT JOIN appointments a ON a.slot_id = s.id AND a.status <> 'cancelled'
LEFT JOIN users st ON st.id = a.student_id
"""


def load_appt(conn: Any, appt_id: UUID, user: dict) -> dict:
    """The appointment, but only if `user` is its student or its advisor. Anyone else gets 404, so
    the existence of other people's appointments is not revealed."""
    row = one(
        conn,
        APPT_SELECT + " WHERE a.id = %(id)s AND (a.student_id = %(uid)s OR a.advisor_id = %(uid)s)",
        {"id": appt_id, "uid": user["id"]},
    )
    if row is None:
        raise ApiError(404, "appointment_not_found", "ไม่พบนัดหมายนี้")
    return row


def shape_appt(r: dict) -> dict:
    return {
        "id": r["id"],
        "status": r["status"],
        "topic": r["topic"],
        "cancel_reason": r["cancel_reason"] or None,
        "slot_id": r["slot_id"],
        "starts_at": r["starts_at"],
        "ends_at": r["ends_at"],
        "mode": r["mode"],
        "location": r["location"],
        "meeting_url": r["meeting_url"],
        "advisor": {"id": r["advisor_id"], "name": r["advisor_name"], "department": r["department"]},
        "student": {"id": r["student_id"], "name": r["student_name"]},
        "created_at": r["created_at"],
        "updated_at": r["updated_at"],
    }


def shape_slot(r: dict, *, show_student: bool) -> dict:
    out = {
        "id": r["id"],
        "advisor": {"id": r["advisor_id"], "name": r["advisor_name"], "department": r["department"]},
        "starts_at": r["starts_at"],
        "ends_at": r["ends_at"],
        "mode": r["mode"],
        "location": r["location"],
        "meeting_url": r["meeting_url"],
        "status": r["status"],
    }
    if show_student:
        out["appointment_id"] = r["appointment_id"]
        out["student_name"] = r["student_name"]
    return out
