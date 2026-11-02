from uuid import UUID

from fastapi import APIRouter, Depends

from ..db import get_conn, one
from ..deps import require_roles
from ..errors import ApiError
from ..notify import fmt_when, notify
from ..schemas import NotePatch

router = APIRouter(prefix="/notes", tags=["notes"])


@router.patch("/{note_id}")
def update_note(note_id: UUID, body: NotePatch, user=Depends(require_roles("advisor")), conn=Depends(get_conn)):
    """Edit a note. Fields left out stay as they are; send "" to clear a text field. Switching a note
    to `shared` notifies the student, and only the first time for that appointment."""
    found = one(
        conn,
        """
        SELECT n.id, n.appointment_id, a.advisor_id, a.student_id, a.topic, s.starts_at
        FROM advising_notes n
        JOIN appointments a ON a.id = n.appointment_id
        JOIN availability_slots s ON s.id = a.slot_id
        WHERE n.id = %(id)s
        """,
        {"id": note_id},
    )
    if found is None or found["advisor_id"] != user["id"]:
        raise ApiError(404, "note_not_found", "ไม่พบบันทึกนี้")
    with conn.transaction():
        note = one(
            conn,
            """
            UPDATE advising_notes
            SET issues = COALESCE(%(issues)s::text, issues),
                summary = COALESCE(%(summary)s::text, summary),
                visibility = COALESCE(%(visibility)s::text, visibility),
                updated_at = now()
            WHERE id = %(id)s
            RETURNING id, appointment_id, author_id, issues, summary, visibility, created_at, updated_at
            """,
            {"id": note_id, "issues": body.issues, "summary": body.summary, "visibility": body.visibility},
        )
        if note["visibility"] == "shared":
            notify(
                conn,
                found["student_id"],
                "summary",
                "อาจารย์บันทึกสรุปนัดแล้ว",
                f"{fmt_when(found['starts_at'])} · {found['topic']}",
                found["appointment_id"],
                dedupe_key=f"sum:{found['appointment_id']}",
            )
    return note
