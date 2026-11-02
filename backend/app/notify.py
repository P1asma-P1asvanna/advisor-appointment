"""Small helpers for writing notifications from the API."""
from datetime import datetime
from typing import Any
from uuid import UUID

from .db import run


def fmt_when(dt: datetime) -> str:
    """'2/11 09:00' in the connection's time zone."""
    return f"{dt.day}/{dt.month} {dt:%H:%M}"


def notify(
    conn: Any,
    user_id: UUID,
    type_: str,
    title: str,
    body: str | None = None,
    appointment_id: UUID | None = None,
    dedupe_key: str | None = None,
) -> bool:
    """Insert a notification. With a dedupe_key the same event is stored only once per user.
    Returns True when a row was inserted."""
    n = run(
        conn,
        """
        INSERT INTO notifications (user_id, type, title, body, appointment_id, dedupe_key)
        VALUES (%(user_id)s, %(type)s, %(title)s, %(body)s, %(appointment_id)s, %(dedupe_key)s)
        ON CONFLICT (user_id, dedupe_key) DO NOTHING
        """,
        {
            "user_id": user_id,
            "type": type_,
            "title": title,
            "body": body,
            "appointment_id": appointment_id,
            "dedupe_key": dedupe_key,
        },
    )
    return n == 1
