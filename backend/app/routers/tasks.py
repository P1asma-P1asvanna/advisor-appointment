from uuid import UUID

from fastapi import APIRouter, Depends

from ..db import get_conn, many, one
from ..deps import require_roles
from ..errors import ApiError
from ..notify import notify
from ..repo import load_appt
from ..schemas import TaskIn, TaskPatch

router = APIRouter(tags=["tasks"])

TASK_STATUSES = ("todo", "doing", "done", "cancelled")

TASK_SELECT = """
SELECT t.id, t.appointment_id, t.note_id, t.title, t.description, t.due_date, t.status,
       t.completed_at, t.created_at,
       COALESCE(t.status IN ('todo', 'doing') AND t.due_date < current_date, false) AS is_overdue,
       a.topic AS appointment_topic,
       t.assignee_id, asg.full_name AS assignee_name,
       t.created_by, cr.full_name AS created_by_name
FROM tasks t
JOIN appointments a ON a.id = t.appointment_id
JOIN users asg ON asg.id = t.assignee_id
JOIN users cr ON cr.id = t.created_by
"""


@router.get("/tasks")
def list_tasks(
    status: str | None = None,
    appointment_id: UUID | None = None,
    user=Depends(require_roles("student", "advisor")),
    conn=Depends(get_conn),
):
    """Students see tasks assigned to them, advisors the tasks they created.
    Cancelled tasks are hidden unless `status=cancelled` is asked for."""
    if status is not None and status not in TASK_STATUSES:
        raise ApiError(422, "invalid_status", "สถานะต้องเป็น todo, doing, done หรือ cancelled")
    rows = many(
        conn,
        TASK_SELECT
        + """
        WHERE (t.assignee_id = %(uid)s OR t.created_by = %(uid)s)
          AND ((%(status)s::text IS NULL AND t.status <> 'cancelled') OR t.status = %(status)s::text)
          AND (%(appointment_id)s::uuid IS NULL OR t.appointment_id = %(appointment_id)s::uuid)
        ORDER BY (t.status = 'done'), t.due_date NULLS LAST, t.created_at
        """,
        {"uid": user["id"], "status": status, "appointment_id": appointment_id},
    )
    return {"items": rows}


@router.post("/appointments/{appointment_id}/tasks", status_code=201)
def create_task(appointment_id: UUID, body: TaskIn, user=Depends(require_roles("advisor")), conn=Depends(get_conn)):
    """Give the student a follow-up task for this appointment."""
    appt = load_appt(conn, appointment_id, user)
    if appt["status"] == "cancelled":
        raise ApiError(409, "appointment_cancelled", "นัดนี้ถูกยกเลิกแล้ว มอบงานไม่ได้")
    if body.note_id is not None:
        ok = one(
            conn,
            "SELECT 1 AS x FROM advising_notes WHERE id = %(note)s AND appointment_id = %(appt)s",
            {"note": body.note_id, "appt": appointment_id},
        )
        if ok is None:
            raise ApiError(422, "invalid_note", "บันทึกที่อ้างถึงไม่ใช่ของนัดนี้")
    with conn.transaction():
        created = one(
            conn,
            """
            INSERT INTO tasks (appointment_id, note_id, assignee_id, created_by, title, description, due_date)
            VALUES (%(appt)s, %(note)s, %(assignee)s, %(creator)s, %(title)s, %(description)s, %(due)s)
            RETURNING id
            """,
            {
                "appt": appointment_id,
                "note": body.note_id,
                "assignee": appt["student_id"],
                "creator": user["id"],
                "title": body.title,
                "description": body.description,
                "due": body.due_date,
            },
        )
        notify(conn, appt["student_id"], "task", "อาจารย์มอบหมายงานใหม่", body.title, appointment_id)
    return one(conn, TASK_SELECT + " WHERE t.id = %(id)s", {"id": created["id"]})


@router.patch("/tasks/{task_id}")
def update_task(task_id: UUID, body: TaskPatch, user=Depends(require_roles("student", "advisor")), conn=Depends(get_conn)):
    """Move a task between todo / doing / done. The student who owns the task may change only its status
    (and not to `cancelled`); the advisor who created it may also edit title, description and due date."""
    task = one(
        conn,
        "SELECT id, appointment_id, created_by, assignee_id, status, title FROM tasks "
        "WHERE id = %(id)s AND (assignee_id = %(uid)s OR created_by = %(uid)s)",
        {"id": task_id, "uid": user["id"]},
    )
    if task is None:
        raise ApiError(404, "task_not_found", "ไม่พบงานนี้")
    is_creator = task["created_by"] == user["id"]
    if not is_creator:
        if body.title is not None or body.description is not None or body.due_date is not None:
            raise ApiError(403, "forbidden_fields", "นักศึกษาเปลี่ยนได้เฉพาะสถานะของงาน")
        if body.status == "cancelled":
            raise ApiError(403, "forbidden_fields", "นักศึกษายกเลิกงานเองไม่ได้")
    with conn.transaction():
        one(
            conn,
            """
            UPDATE tasks
            SET status = COALESCE(%(status)s::text, status),
                title = COALESCE(%(title)s::text, title),
                description = COALESCE(%(description)s::text, description),
                due_date = COALESCE(%(due_date)s::date, due_date),
                completed_at = CASE WHEN COALESCE(%(status)s::text, status) = 'done'
                                    THEN COALESCE(completed_at, now()) ELSE NULL END
            WHERE id = %(id)s
            RETURNING id
            """,
            {
                "id": task_id,
                "status": body.status,
                "title": body.title,
                "description": body.description,
                "due_date": body.due_date,
            },
        )
        if not is_creator and body.status == "done" and task["status"] != "done":
            notify(
                conn,
                task["created_by"],
                "task",
                f"{user['full_name']} ทำงานเสร็จแล้ว",
                task["title"],
                task["appointment_id"],
            )
    return one(conn, TASK_SELECT + " WHERE t.id = %(id)s", {"id": task_id})
