from datetime import datetime, timezone
from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends

from ..db import get_conn, many, one, run
from ..deps import require_roles
from ..errors import ApiError
from ..notify import fmt_when, notify
from ..repo import APPT_SELECT, load_appt, shape_appt
from ..schemas import BookIn, CancelIn, NoteIn, StatusIn, TopicPatch

router = APIRouter(prefix="/appointments", tags=["appointments"])

PARTICIPANTS = ("student", "advisor")


@router.post("", status_code=201)
def book(body: BookIn, user=Depends(require_roles("student")), conn=Depends(get_conn)):
    """Book an open slot. The rules (notice period, limit per student, time clashes) are enforced
    inside the database function book_slot(), which also notifies the student and the advisor."""
    row = one(
        conn,
        "SELECT book_slot(%(slot)s, %(student)s, %(topic)s) AS id",
        {"slot": body.slot_id, "student": user["id"], "topic": body.topic},
    )
    return shape_appt(load_appt(conn, row["id"], user))


@router.get("")
def list_appointments(
    view: Literal["upcoming", "past", "all"] = "all",
    status: str | None = None,
    limit: int = 100,
    user=Depends(require_roles(*PARTICIPANTS)),
    conn=Depends(get_conn),
):
    """My appointments (as student or as advisor). `upcoming` = pending/confirmed and not started yet."""
    rows = many(
        conn,
        APPT_SELECT
        + """
        WHERE (a.student_id = %(uid)s OR a.advisor_id = %(uid)s)
          AND (%(status)s::text IS NULL OR a.status = %(status)s::text)
          AND (
                %(view)s::text = 'all'
             OR (%(view)s::text = 'upcoming' AND a.status IN ('pending', 'confirmed') AND s.starts_at > now())
             OR (%(view)s::text = 'past' AND NOT (a.status IN ('pending', 'confirmed') AND s.starts_at > now()))
          )
        ORDER BY (CASE WHEN %(view)s::text = 'upcoming' THEN s.starts_at END) ASC NULLS LAST,
                 s.starts_at DESC
        LIMIT %(limit)s
        """,
        {"uid": user["id"], "status": status, "view": view, "limit": max(1, min(limit, 500))},
    )
    return {"items": [shape_appt(r) for r in rows]}


@router.get("/{appointment_id}")
def get_appointment(appointment_id: UUID, user=Depends(require_roles(*PARTICIPANTS)), conn=Depends(get_conn)):
    """One appointment with its notes and follow-up tasks. A student sees only notes marked `shared`."""
    appt = load_appt(conn, appointment_id, user)
    notes = many(
        conn,
        """
        SELECT id, author_id, issues, summary, visibility, created_at, updated_at
        FROM advising_notes
        WHERE appointment_id = %(id)s AND (%(is_advisor)s::bool OR visibility = 'shared')
        ORDER BY created_at
        """,
        {"id": appointment_id, "is_advisor": user["role"] == "advisor"},
    )
    tasks = many(
        conn,
        """
        SELECT id, note_id, title, description, due_date, status, completed_at,
               COALESCE(status IN ('todo', 'doing') AND due_date < current_date, false) AS is_overdue
        FROM tasks
        WHERE appointment_id = %(id)s AND status <> 'cancelled'
        ORDER BY created_at
        """,
        {"id": appointment_id},
    )
    return {**shape_appt(appt), "notes": notes, "tasks": tasks}


@router.patch("/{appointment_id}")
def update_topic(appointment_id: UUID, body: TopicPatch, user=Depends(require_roles("student")), conn=Depends(get_conn)):
    """The student fixes the topic of their own appointment until it starts. The advisor is told."""
    appt = load_appt(conn, appointment_id, user)
    if appt["student_id"] != user["id"]:
        raise ApiError(404, "appointment_not_found", "ไม่พบนัดหมายนี้")
    if appt["status"] not in ("pending", "confirmed") or appt["starts_at"] <= datetime.now(timezone.utc):
        raise ApiError(409, "not_editable", "นัดนี้เริ่มแล้วหรือปิดไปแล้ว แก้หัวข้อไม่ได้")
    with conn.transaction():
        run(conn, "UPDATE appointments SET topic = %(t)s, updated_at = now() WHERE id = %(id)s",
            {"t": body.topic, "id": appointment_id})
        if body.topic != appt["topic"]:
            notify(conn, appt["advisor_id"], "system", "นักศึกษาแก้หัวข้อนัด",
                   f"{fmt_when(appt['starts_at'])} · {body.topic}", appointment_id)
    return shape_appt(load_appt(conn, appointment_id, user))


@router.post("/{appointment_id}/cancel")
def cancel(appointment_id: UUID, body: CancelIn, user=Depends(require_roles(*PARTICIPANTS)), conn=Depends(get_conn)):
    """Cancel an appointment. Students must respect the cancel deadline; advisors must give a reason.
    The slot becomes bookable again and the other side is notified (done by cancel_appointment())."""
    load_appt(conn, appointment_id, user)  # 404 unless the caller is a participant
    reason = (body.reason or "").strip()
    if user["role"] == "advisor" and not reason:
        raise ApiError(422, "reason_required", "ใส่เหตุผลก่อนยกเลิก เพื่อให้นักศึกษารับทราบ")
    run(
        conn,
        "SELECT cancel_appointment(%(id)s, %(by)s, %(reason)s)",
        {"id": appointment_id, "by": user["id"], "reason": reason or "ไม่ระบุเหตุผล"},
    )
    return shape_appt(load_appt(conn, appointment_id, user))


@router.post("/{appointment_id}/status")
def set_status(appointment_id: UUID, body: StatusIn, user=Depends(require_roles("advisor")), conn=Depends(get_conn)):
    """Advisor closes an appointment as `completed` or `no_show` (no_show only after it has started)."""
    appt = load_appt(conn, appointment_id, user)
    if appt["status"] not in ("pending", "confirmed"):
        raise ApiError(409, "not_active", "นัดนี้ปิดไปแล้ว เปลี่ยนสถานะไม่ได้")
    if body.status == "no_show" and appt["starts_at"] > datetime.now(timezone.utc):
        raise ApiError(409, "too_early", "ยังไม่ถึงเวลานัด บันทึกว่าไม่มาตามนัดไม่ได้")
    with conn.transaction():
        changed = run(
            conn,
            """
            UPDATE appointments SET status = %(status)s, updated_at = now()
            WHERE id = %(id)s AND status IN ('pending', 'confirmed')
            """,
            {"status": body.status, "id": appointment_id},
        )
        if changed == 0:
            raise ApiError(409, "not_active", "นัดนี้ปิดไปแล้ว เปลี่ยนสถานะไม่ได้")
        if body.status == "no_show":
            notify(
                conn,
                appt["student_id"],
                "no_show",
                "บันทึกว่าไม่มาตามนัด",
                f"{fmt_when(appt['starts_at'])} · {appt['topic']}",
                appointment_id,
            )
    return shape_appt(load_appt(conn, appointment_id, user))


@router.post("/{appointment_id}/notes", status_code=201)
def add_note(appointment_id: UUID, body: NoteIn, user=Depends(require_roles("advisor")), conn=Depends(get_conn)):
    """Record what was discussed. A `shared` note notifies the student (once per appointment)."""
    appt = load_appt(conn, appointment_id, user)
    with conn.transaction():
        note = one(
            conn,
            """
            INSERT INTO advising_notes (appointment_id, author_id, issues, summary, visibility)
            VALUES (%(appt)s, %(author)s, %(issues)s, %(summary)s, %(visibility)s)
            RETURNING id, appointment_id, author_id, issues, summary, visibility, created_at, updated_at
            """,
            {
                "appt": appointment_id,
                "author": user["id"],
                "issues": body.issues,
                "summary": body.summary,
                "visibility": body.visibility,
            },
        )
        if body.visibility == "shared":
            notify(
                conn,
                appt["student_id"],
                "summary",
                "อาจารย์บันทึกสรุปนัดแล้ว",
                f"{fmt_when(appt['starts_at'])} · {appt['topic']}",
                appointment_id,
                dedupe_key=f"sum:{appointment_id}",
            )
    return note
