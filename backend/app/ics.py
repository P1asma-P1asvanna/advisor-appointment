"""Minimal iCalendar (RFC 5545) writer so an appointment can be added to Google/Apple/Outlook calendars."""
from datetime import datetime, timezone

PRODID = "-//Advisor Appointment//TH"


def _esc(text: str) -> str:
    return (text.replace("\\", "\\\\").replace(";", "\;").replace(",", "\\,")
            .replace("\r\n", "\n").replace("\r", "\n").replace("\n", "\\n"))


def _fold(line: str) -> list[str]:
    """Lines are limited to 75 octets; continuation lines start with one space. Never split a UTF-8 character."""
    out, cur, size = [], "", 0
    for ch in line:
        n = len(ch.encode("utf-8"))
        if size + n > (75 if not out else 74):
            out.append(cur)
            cur, size = "", 0
        cur += ch
        size += n
    out.append(cur)
    return [out[0]] + [" " + p for p in out[1:]]


def _utc(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def event_fields(appt: dict, role: str) -> dict:
    """Title/description/location shared by the .ics file (shape_appt output) and the UI's Google link."""
    other = appt["student"]["name"] if role == "advisor" else appt["advisor"]["name"]
    where = appt["location"] if appt["mode"] == "onsite" else (appt["meeting_url"] or "ออนไลน์")
    desc = [f"หัวข้อ: {appt['topic']}", ("นักศึกษา: " if role == "advisor" else "อาจารย์: ") + other]
    if appt["mode"] != "onsite" and appt["meeting_url"]:
        desc.append("ลิงก์ประชุม: " + appt["meeting_url"])
    return {"title": f"นัดพบอาจารย์ที่ปรึกษา: {other}" if role == "student" else f"นัดพบนักศึกษา: {other}",
            "description": "\n".join(desc), "location": where or ""}


def build_calendar(appts: list[dict], role: str) -> bytes:
    lines = ["BEGIN:VCALENDAR", "VERSION:2.0", f"PRODID:{PRODID}", "CALSCALE:GREGORIAN", "METHOD:PUBLISH",
             "X-WR-CALNAME:นัดหมายอาจารย์", "X-WR-TIMEZONE:Asia/Bangkok"]
    for a in appts:
        f = event_fields(a, role)
        lines += [
            "BEGIN:VEVENT",
            f"UID:{a['id']}@advisor-appointment",
            f"DTSTAMP:{_utc(a['updated_at'])}",
            f"DTSTART:{_utc(a['starts_at'])}",
            f"DTEND:{_utc(a['ends_at'])}",
            f"SUMMARY:{_esc(f['title'])}",
            f"DESCRIPTION:{_esc(f['description'])}",
            f"LOCATION:{_esc(f['location'])}",
            "STATUS:" + ("CONFIRMED" if a["status"] == "confirmed" else "TENTATIVE" if a["status"] == "pending" else "CANCELLED"),
            "BEGIN:VALARM", "ACTION:DISPLAY", "DESCRIPTION:นัดหมายอาจารย์ในอีก 1 ชั่วโมง", "TRIGGER:-PT1H", "END:VALARM",
            "END:VEVENT",
        ]
    lines.append("END:VCALENDAR")
    folded = [p for ln in lines for p in _fold(ln)]
    return ("\r\n".join(folded) + "\r\n").encode("utf-8")
