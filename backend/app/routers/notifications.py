from uuid import UUID

from fastapi import APIRouter, Depends

from ..db import get_conn, many, one, run
from ..deps import current_user
from ..errors import ApiError

router = APIRouter(prefix="/notifications", tags=["notifications"])

COLUMNS = "id, type, title, body, appointment_id, created_at, read_at"


@router.get("")
def list_notifications(
    unread_only: bool = False,
    limit: int = 50,
    user=Depends(current_user),
    conn=Depends(get_conn),
):
    """My inbox, newest first, plus the unread count for the badge."""
    items = many(
        conn,
        f"""
        SELECT {COLUMNS} FROM notifications
        WHERE user_id = %(uid)s AND (NOT %(unread_only)s::bool OR read_at IS NULL)
        ORDER BY created_at DESC
        LIMIT %(limit)s
        """,
        {"uid": user["id"], "unread_only": unread_only, "limit": max(1, min(limit, 200))},
    )
    unread = one(
        conn,
        "SELECT count(*) AS n FROM notifications WHERE user_id = %(uid)s AND read_at IS NULL",
        {"uid": user["id"]},
    )["n"]
    return {"items": items, "unread": unread}


@router.post("/read-all")
def read_all(user=Depends(current_user), conn=Depends(get_conn)):
    n = run(
        conn,
        "UPDATE notifications SET read_at = now() WHERE user_id = %(uid)s AND read_at IS NULL",
        {"uid": user["id"]},
    )
    return {"marked": n}


@router.post("/{notification_id}/read")
def mark_read(notification_id: UUID, user=Depends(current_user), conn=Depends(get_conn)):
    row = one(
        conn,
        f"""
        UPDATE notifications SET read_at = COALESCE(read_at, now())
        WHERE id = %(id)s AND user_id = %(uid)s
        RETURNING {COLUMNS}
        """,
        {"id": notification_id, "uid": user["id"]},
    )
    if row is None:
        raise ApiError(404, "notification_not_found", "ไม่พบการแจ้งเตือนนี้")
    return row
