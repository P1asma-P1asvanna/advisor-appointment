"""Request bodies. Responses are plain dicts built from SQL rows (see repo.py)."""
from datetime import date
from typing import Annotated, Literal, Optional
from uuid import UUID

from pydantic import AwareDatetime, BaseModel, Field, StringConstraints, model_validator

Text300 = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=300)]
Title200 = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]
LongText = Annotated[str, StringConstraints(max_length=5000)]


class LoginIn(BaseModel):
    email: Annotated[str, StringConstraints(strip_whitespace=True, to_lower=True, min_length=3, max_length=254)]
    password: Annotated[str, StringConstraints(min_length=1, max_length=200)]
    # Optional: the tab the user picked on the login screen. A mismatch is rejected with role_mismatch.
    role: Optional[Literal["student", "advisor", "admin"]] = None


class SlotIn(BaseModel):
    starts_at: AwareDatetime
    ends_at: AwareDatetime
    mode: Literal["onsite", "online"] = "onsite"
    location: Optional[Annotated[str, StringConstraints(strip_whitespace=True, max_length=200)]] = None
    meeting_url: Optional[Annotated[str, StringConstraints(strip_whitespace=True, max_length=500)]] = None

    @model_validator(mode="after")
    def _check_duration(self):
        minutes = (self.ends_at - self.starts_at).total_seconds() / 60
        if minutes < 10 or minutes > 240:
            raise ValueError("a slot must last between 10 and 240 minutes")
        return self


class BookIn(BaseModel):
    slot_id: UUID
    topic: Text300


class CancelIn(BaseModel):
    reason: Optional[Annotated[str, StringConstraints(strip_whitespace=True, max_length=300)]] = None


class StatusIn(BaseModel):
    status: Literal["completed", "no_show"]


class NoteIn(BaseModel):
    issues: Optional[LongText] = None
    summary: Optional[LongText] = None
    visibility: Literal["private", "shared"] = "shared"

    @model_validator(mode="after")
    def _not_empty(self):
        if not (self.issues or "").strip() and not (self.summary or "").strip():
            raise ValueError("provide issues or summary")
        return self


class NotePatch(BaseModel):
    """Fields left out stay unchanged. Send an empty string to clear a text field."""

    issues: Optional[LongText] = None
    summary: Optional[LongText] = None
    visibility: Optional[Literal["private", "shared"]] = None

    @model_validator(mode="after")
    def _something(self):
        if self.issues is None and self.summary is None and self.visibility is None:
            raise ValueError("nothing to update")
        return self


class TaskIn(BaseModel):
    title: Title200
    description: Optional[LongText] = None
    due_date: Optional[date] = None
    note_id: Optional[UUID] = None


class TaskPatch(BaseModel):
    """Students may change only `status`. Advisors (the task's creator) may change everything."""

    status: Optional[Literal["todo", "doing", "done", "cancelled"]] = None
    title: Optional[Title200] = None
    description: Optional[LongText] = None
    due_date: Optional[date] = None

    @model_validator(mode="after")
    def _something(self):
        if all(v is None for v in (self.status, self.title, self.description, self.due_date)):
            raise ValueError("nothing to update")
        return self


class PolicyIn(BaseModel):
    department: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=120)] = "*"
    min_notice_hours: int = Field(ge=0, le=720)
    cancel_before_hours: int = Field(ge=0, le=720)
    max_active_per_student: int = Field(ge=1, le=20)
    reminder_hours_before: int = Field(ge=1, le=168)
