from fastapi import APIRouter, Depends

from ..db import get_conn, many, one
from ..deps import current_user, require_roles
from ..schemas import PolicyIn

router = APIRouter(tags=["admin"])


def ratio(n: int, d: int) -> float | None:
    return round(n / d, 4) if d else None


@router.get("/policy")
def effective_policy(department: str | None = None, user=Depends(current_user), conn=Depends(get_conn)):
    """The booking rules that apply to a department (falls back to the default row '*').
    Students use this to show the rules and compute how long they can still book or cancel."""
    return one(
        conn,
        "SELECT * FROM policy_for(COALESCE(%(department)s::text, '*'))",
        {"department": department},
    )


@router.put("/admin/policy")
def save_policy(body: PolicyIn, user=Depends(require_roles("admin")), conn=Depends(get_conn)):
    """Set the rules for one department, or for all of them with department='*'."""
    return one(
        conn,
        """
        INSERT INTO booking_policies
            (department, min_notice_hours, cancel_before_hours, max_active_per_student, reminder_hours_before, updated_by)
        VALUES (%(department)s, %(min_notice_hours)s, %(cancel_before_hours)s, %(max_active_per_student)s,
                %(reminder_hours_before)s, %(uid)s)
        ON CONFLICT (department) DO UPDATE SET
            min_notice_hours = EXCLUDED.min_notice_hours,
            cancel_before_hours = EXCLUDED.cancel_before_hours,
            max_active_per_student = EXCLUDED.max_active_per_student,
            reminder_hours_before = EXCLUDED.reminder_hours_before,
            updated_by = EXCLUDED.updated_by,
            updated_at = now()
        RETURNING *
        """,
        {**body.model_dump(), "uid": user["id"]},
    )


WATCHLIST_SQL = """
SELECT * FROM (
  SELECT st.id, st.full_name,
    (SELECT count(*) FROM appointments a JOIN users adv ON adv.id = a.advisor_id
      WHERE a.student_id = st.id AND a.status = 'no_show'
        AND (%(dept)s::text IS NULL OR adv.department = %(dept)s::text)) AS no_shows,
    (SELECT count(*) FROM tasks t JOIN users cr ON cr.id = t.created_by
      WHERE t.assignee_id = st.id AND t.status IN ('todo', 'doing') AND t.due_date < current_date
        AND (%(dept)s::text IS NULL OR cr.department = %(dept)s::text)) AS overdue_tasks
  FROM users st WHERE st.role = 'student'
) w
WHERE no_shows > 0 OR overdue_tasks > 0
ORDER BY no_shows DESC, overdue_tasks DESC, full_name
"""


@router.get("/admin/overview")
def overview(department: str | None = None, user=Depends(require_roles("admin")), conn=Depends(get_conn)):
    """Department overview: headline numbers, one row per advisor, and students worth following up.
    Only counts and names are returned. Appointment topics and notes are never exposed here."""
    p = {"dept": department}
    advisors = many(
        conn,
        """
        SELECT * FROM v_advisor_stats
        WHERE (%(dept)s::text IS NULL OR department = %(dept)s::text)
        ORDER BY department, full_name
        """,
        p,
    )
    overdue = one(
        conn,
        """
        SELECT count(*) AS n FROM tasks t JOIN users cr ON cr.id = t.created_by
        WHERE t.status IN ('todo', 'doing') AND t.due_date < current_date
          AND (%(dept)s::text IS NULL OR cr.department = %(dept)s::text)
        """,
        p,
    )["n"]
    total = lambda key: sum(r[key] for r in advisors)  # noqa: E731
    closed = total("appts_completed") + total("appts_no_show")
    departments = [
        r["department"]
        for r in many(
            conn,
            "SELECT DISTINCT department FROM users WHERE role = 'advisor' AND department IS NOT NULL ORDER BY 1",
        )
    ]
    return {
        "department": department,
        "departments": departments,
        "kpis": {
            "slots_total": total("slots_total"),
            "slots_booked": total("slots_booked"),
            "utilization": ratio(total("slots_booked"), total("slots_total")),
            "appts_completed": total("appts_completed"),
            "appts_no_show": total("appts_no_show"),
            "no_show_rate": ratio(total("appts_no_show"), closed),
            "appts_upcoming": total("appts_upcoming"),
            "overdue_tasks": overdue,
        },
        "advisors": [{**r, "utilization": ratio(r["slots_booked"], r["slots_total"])} for r in advisors],
        "watchlist": many(conn, WATCHLIST_SQL, p),
    }


@router.post("/admin/jobs/send-reminders")
def send_reminders(user=Depends(require_roles("admin")), conn=Depends(get_conn)):
    """Create reminders for appointments starting soon and for overdue tasks. Safe to call repeatedly:
    each event is stored once. In production call it every hour from a scheduler (cron, a platform
    scheduler, or `SELECT send_reminders();` straight in psql)."""
    row = one(conn, "SELECT send_reminders() AS created")
    return {"created": row["created"]}
