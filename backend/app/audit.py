"""Append-only trail of admin-relevant changes (table audit_log). Never pass passwords or tokens in `details`."""
import json
from typing import Any

from .db import run


def log(conn: Any, actor: dict | None, action: str, target: dict | None = None, details: dict | None = None) -> None:
    run(
        conn,
        """INSERT INTO audit_log (actor_id, actor_email, action, target_id, target_email, details)
           VALUES (%(aid)s, %(ae)s, %(action)s, %(tid)s, %(te)s, %(d)s)""",
        {
            "aid": actor["id"] if actor else None,
            "ae": actor["email"] if actor else None,
            "action": action,
            "tid": target["id"] if target else None,
            "te": target["email"] if target else None,
            "d": json.dumps(details, ensure_ascii=False, default=str) if details else None,
        },
    )
