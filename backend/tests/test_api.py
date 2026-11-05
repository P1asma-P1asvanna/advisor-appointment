"""HTTP-level tests against a real PostgreSQL database loaded with sql/seed.sql (see conftest.py).

Seed facts these tests rely on (dates are relative to today):
  advisors  อ.สุรีย์พร (วิศวกรรมคอมพิวเตอร์), อ.ณัฐวุฒิ (คณิตศาสตร์)      admin  มาลี
  students  ธนา (1 upcoming appointment), พิมพ์ลดา (2 upcoming = at the default limit of 2)
  open future slots: 4 for อ.สุรีย์พร, 2 for อ.ณัฐวุฒิ, all 2+ days ahead
  16 slots that are not cancelled, 8 of them booked; 4 completed + 1 no_show appointments; 1 overdue task
"""
from datetime import datetime, timedelta, timezone

import pytest

pytestmark = pytest.mark.needs_db

API = "/api/v1"
TZ = timezone(timedelta(hours=7))
ADV1 = "อ.สุรีย์พร"


def at(days, hour, minute=0):
    d = datetime.now(TZ) + timedelta(days=days)
    return d.replace(hour=hour, minute=minute, second=0, microsecond=0).isoformat()


def code(r):
    return r.json()["error"]["code"]


def adv1_open(client, headers):
    items = client.get(f"{API}/slots", headers=headers).json()["items"]
    return sorted((s for s in items if s["advisor"]["name"].startswith(ADV1)), key=lambda s: s["starts_at"])


def upcoming(client, headers):
    return client.get(f"{API}/appointments", params={"view": "upcoming"}, headers=headers).json()["items"]


def by_topic(items, topic):
    return next(i for i in items if i["topic"] == topic)


def inbox(client, headers):
    return client.get(f"{API}/notifications", headers=headers).json()


def set_policy(client, mali, **changes):
    body = {"department": "*", "min_notice_hours": 12, "cancel_before_hours": 12,
            "max_active_per_student": 2, "reminder_hours_before": 24, **changes}
    r = client.put(f"{API}/admin/policy", json=body, headers=mali)
    assert r.status_code == 200, r.text


# ---------------------------------------------------------------- auth

def test_health(client):
    r = client.get("/health")
    assert r.status_code == 200 and r.json() == {"status": "ok"}


def test_login_and_me(client):
    r = client.post(f"{API}/auth/login", json={"email": "Thana@Example.edu", "password": "demo1234", "role": "student"})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["token_type"] == "bearer" and body["user"]["role"] == "student"
    assert "password_hash" not in body["user"]
    me = client.get(f"{API}/me", headers={"Authorization": "Bearer " + body["access_token"]})
    assert me.status_code == 200 and me.json()["email"] == "thana@example.edu"


def test_login_failures(client):
    wrong = client.post(f"{API}/auth/login", json={"email": "thana@example.edu", "password": "nope"})
    unknown = client.post(f"{API}/auth/login", json={"email": "ghost@example.edu", "password": "demo1234"})
    assert wrong.status_code == 401 and unknown.status_code == 401
    assert code(wrong) == code(unknown) == "invalid_credentials"  # same answer: no hint about which emails exist
    mismatch = client.post(f"{API}/auth/login", json={"email": "thana@example.edu", "password": "demo1234", "role": "advisor"})
    assert mismatch.status_code == 403 and code(mismatch) == "role_mismatch"


def test_authentication_required(client):
    assert client.get(f"{API}/me").status_code == 401
    r = client.get(f"{API}/me", headers={"Authorization": "Bearer not-a-token"})
    assert r.status_code == 401 and code(r) == "invalid_token"


# ---------------------------------------------------------------- slots

def test_student_sees_only_open_future_slots(client, thana):
    items = client.get(f"{API}/slots", headers=thana).json()["items"]
    assert len(items) == 6
    assert all(s["status"] == "open" for s in items)
    assert all("appointment_id" not in s and "student_name" not in s for s in items)
    now = datetime.now(TZ)
    assert all(datetime.fromisoformat(s["starts_at"]) > now for s in items)
    only_math = client.get(f"{API}/slots", params={"department": "คณิตศาสตร์"}, headers=thana).json()["items"]
    assert len(only_math) == 2


def test_advisor_sees_only_own_slots_with_students(client, sureeporn):
    items = client.get(f"{API}/slots", headers=sureeporn).json()["items"]
    assert len(items) == 11
    assert all(s["advisor"]["name"].startswith(ADV1) for s in items)
    booked = [s for s in items if s["status"] == "booked"]
    assert booked and all(s["student_name"] for s in booked)


def test_advisor_opens_slot_and_overlap_is_rejected(client, sureeporn):
    body = {"starts_at": at(20, 10), "ends_at": at(20, 10, 30), "mode": "online", "meeting_url": "https://meet.example.edu/x"}
    r = client.post(f"{API}/slots", json=body, headers=sureeporn)
    assert r.status_code == 201, r.text
    assert r.json()["status"] == "open" and r.json()["mode"] == "online"
    clash = client.post(f"{API}/slots", json={**body, "starts_at": at(20, 10, 15), "ends_at": at(20, 10, 45)}, headers=sureeporn)
    assert clash.status_code == 409 and code(clash) == "slot_overlaps"


def test_slot_validation_and_roles(client, sureeporn, thana, mali):
    past = client.post(f"{API}/slots", json={"starts_at": at(-1, 10), "ends_at": at(-1, 10, 30)}, headers=sureeporn)
    assert past.status_code == 422 and code(past) == "slot_in_past"
    short = client.post(f"{API}/slots", json={"starts_at": at(20, 10), "ends_at": at(20, 10, 5)}, headers=sureeporn)
    assert short.status_code == 422 and code(short) == "validation_error"
    for who in (thana, mali):
        r = client.post(f"{API}/slots", json={"starts_at": at(20, 10), "ends_at": at(20, 10, 30)}, headers=who)
        assert r.status_code == 403 and code(r) == "forbidden"


def test_close_slot_rules(client, sureeporn, nattawut):
    items = client.get(f"{API}/slots", headers=sureeporn).json()["items"]
    open_slot = next(s for s in items if s["status"] == "open" and datetime.fromisoformat(s["starts_at"]) > datetime.now(TZ))
    booked = next(s for s in items if s["status"] == "booked")
    assert client.post(f"{API}/slots/{open_slot['id']}/cancel", headers=nattawut).status_code == 404  # not their slot
    ok = client.post(f"{API}/slots/{open_slot['id']}/cancel", headers=sureeporn)
    assert ok.status_code == 200 and ok.json()["status"] == "cancelled"
    again = client.post(f"{API}/slots/{open_slot['id']}/cancel", headers=sureeporn)
    assert again.status_code == 409 and code(again) == "slot_not_open"
    assert code(client.post(f"{API}/slots/{booked['id']}/cancel", headers=sureeporn)) == "slot_not_open"


# ---------------------------------------------------------------- booking

def test_booking_notifies_both_sides_and_hides_the_slot(client, thana, sureeporn):
    slot = adv1_open(client, thana)[0]
    r = client.post(f"{API}/appointments", json={"slot_id": slot["id"], "topic": "  ทดสอบจอง  "}, headers=thana)
    assert r.status_code == 201, r.text
    appt = r.json()
    assert appt["status"] == "confirmed" and appt["topic"] == "ทดสอบจอง"
    assert appt["advisor"]["name"].startswith(ADV1) and appt["student"]["name"] == "ธนา ศรีสุข"
    assert slot["id"] not in [s["id"] for s in adv1_open(client, thana)]
    for headers in (sureeporn, thana):
        assert any(n["type"] == "booked" and n["appointment_id"] == appt["id"] for n in inbox(client, headers)["items"])


def test_taken_slot_is_rejected(client, thana, pimlada):
    slot = adv1_open(client, thana)[0]
    assert client.post(f"{API}/appointments", json={"slot_id": slot["id"], "topic": "a"}, headers=thana).status_code == 201
    second = client.post(f"{API}/appointments", json={"slot_id": slot["id"], "topic": "b"}, headers=pimlada)
    assert second.status_code == 409 and code(second) == "slot_unavailable"


def test_booking_limit(client, pimlada):
    slot = adv1_open(client, pimlada)[0]
    r = client.post(f"{API}/appointments", json={"slot_id": slot["id"], "topic": "one too many"}, headers=pimlada)
    assert r.status_code == 409 and code(r) == "too_many_active_appointments"


def test_student_cannot_hold_two_appointments_at_the_same_time(client, thana, nattawut):
    mine = upcoming(client, thana)[0]
    r = client.post(f"{API}/slots", json={"starts_at": mine["starts_at"], "ends_at": mine["ends_at"]}, headers=nattawut)
    assert r.status_code == 201, r.text
    clash = client.post(f"{API}/appointments", json={"slot_id": r.json()["id"], "topic": "same time"}, headers=thana)
    assert clash.status_code == 409 and code(clash) == "student_time_conflict"


def test_booking_notice_rule_follows_the_policy(client, thana, mali):
    set_policy(client, mali, min_notice_hours=720)
    slot = adv1_open(client, thana)[0]
    r = client.post(f"{API}/appointments", json={"slot_id": slot["id"], "topic": "too soon"}, headers=thana)
    assert r.status_code == 409 and code(r) == "too_late_to_book"


def test_only_students_book_and_input_is_validated(client, sureeporn, thana):
    slot = adv1_open(client, thana)[0]
    assert client.post(f"{API}/appointments", json={"slot_id": slot["id"], "topic": "x"}, headers=sureeporn).status_code == 403
    blank = client.post(f"{API}/appointments", json={"slot_id": slot["id"], "topic": "   "}, headers=thana)
    assert blank.status_code == 422 and code(blank) == "validation_error"
    bad_id = client.post(f"{API}/appointments", json={"slot_id": "not-a-uuid", "topic": "x"}, headers=thana)
    assert bad_id.status_code == 422


# ---------------------------------------------------------------- reading appointments

def test_my_appointments_and_privacy(client, thana, pimlada, sureeporn, nattawut, mali):
    assert len(upcoming(client, thana)) == 1
    assert len(upcoming(client, pimlada)) == 2
    assert len(upcoming(client, sureeporn)) == 2
    appt = upcoming(client, thana)[0]
    assert client.get(f"{API}/appointments/{appt['id']}", headers=thana).status_code == 200
    for outsider in (pimlada, nattawut):
        r = client.get(f"{API}/appointments/{appt['id']}", headers=outsider)
        assert r.status_code == 404 and code(r) == "appointment_not_found"
    assert client.get(f"{API}/appointments", headers=mali).status_code == 403  # admin sees counts only


def test_appointment_detail_has_notes_and_tasks(client, thana):
    past = client.get(f"{API}/appointments", params={"view": "past"}, headers=thana).json()["items"]
    first = by_topic(past, "แผนการเรียนและการฝึกงาน")
    detail = client.get(f"{API}/appointments/{first['id']}", headers=thana).json()
    assert len(detail["notes"]) == 1 and detail["notes"][0]["visibility"] == "shared"
    assert len(detail["tasks"]) == 3
    assert sum(t["is_overdue"] for t in detail["tasks"]) == 1


# ---------------------------------------------------------------- cancelling

def test_student_cancel_frees_the_slot_and_notifies_the_advisor(client, thana, sureeporn):
    appt = upcoming(client, thana)[0]
    r = client.post(f"{API}/appointments/{appt['id']}/cancel", json={"reason": "ติดสอบ"}, headers=thana)
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "cancelled" and r.json()["cancel_reason"] == "ติดสอบ"
    assert appt["slot_id"] in [s["id"] for s in adv1_open(client, thana)]
    assert any(n["type"] == "cancelled" and n["appointment_id"] == appt["id"] for n in inbox(client, sureeporn)["items"])
    assert code(client.post(f"{API}/appointments/{appt['id']}/cancel", json={}, headers=thana)) == "not_cancellable"


def test_cancel_deadline_binds_students_not_advisors(client, thana, sureeporn, mali):
    set_policy(client, mali, cancel_before_hours=720)
    appt = upcoming(client, thana)[0]
    late = client.post(f"{API}/appointments/{appt['id']}/cancel", json={"reason": "x"}, headers=thana)
    assert late.status_code == 409 and code(late) == "too_late_to_cancel"
    ok = client.post(f"{API}/appointments/{appt['id']}/cancel", json={"reason": "ติดประชุมภาค"}, headers=sureeporn)
    assert ok.status_code == 200 and ok.json()["status"] == "cancelled"


def test_cancel_permissions(client, thana, pimlada, sureeporn):
    appt = upcoming(client, thana)[0]
    assert client.post(f"{API}/appointments/{appt['id']}/cancel", json={"reason": "x"}, headers=pimlada).status_code == 404
    no_reason = client.post(f"{API}/appointments/{appt['id']}/cancel", json={}, headers=sureeporn)
    assert no_reason.status_code == 422 and code(no_reason) == "reason_required"


# ---------------------------------------------------------------- closing an appointment

def test_advisor_closes_appointments(client, thana, sureeporn):
    appt = by_topic(upcoming(client, sureeporn), "ปรึกษาเลือกวิชาเลือกเทอม 2")
    early = client.post(f"{API}/appointments/{appt['id']}/status", json={"status": "no_show"}, headers=sureeporn)
    assert early.status_code == 409 and code(early) == "too_early"
    assert client.post(f"{API}/appointments/{appt['id']}/status", json={"status": "completed"}, headers=thana).status_code == 403
    done = client.post(f"{API}/appointments/{appt['id']}/status", json={"status": "completed"}, headers=sureeporn)
    assert done.status_code == 200 and done.json()["status"] == "completed"
    again = client.post(f"{API}/appointments/{appt['id']}/status", json={"status": "completed"}, headers=sureeporn)
    assert again.status_code == 409 and code(again) == "not_active"
    bad = client.post(f"{API}/appointments/{appt['id']}/status", json={"status": "confirmed"}, headers=sureeporn)
    assert bad.status_code == 422


# ---------------------------------------------------------------- notes

def test_private_notes_are_hidden_and_sharing_notifies_once(client, thana, sureeporn):
    appt = by_topic(upcoming(client, sureeporn), "ปรึกษาเลือกวิชาเลือกเทอม 2")
    url = f"{API}/appointments/{appt['id']}"
    created = client.post(f"{url}/notes", json={"issues": "กังวลเรื่องเกรด", "summary": "นัดติดตามอีกครั้ง", "visibility": "private"}, headers=sureeporn)
    assert created.status_code == 201, created.text
    note_id = created.json()["id"]
    assert client.get(url, headers=thana).json()["notes"] == []
    assert len(client.get(url, headers=sureeporn).json()["notes"]) == 1

    def summaries():
        return [n for n in inbox(client, thana)["items"] if n["type"] == "summary" and n["appointment_id"] == appt["id"]]

    assert summaries() == []  # a private note tells the student nothing
    shared = client.patch(f"{API}/notes/{note_id}", json={"visibility": "shared"}, headers=sureeporn)
    assert shared.status_code == 200 and shared.json()["visibility"] == "shared"
    assert len(client.get(url, headers=thana).json()["notes"]) == 1
    assert len(summaries()) == 1
    client.patch(f"{API}/notes/{note_id}", json={"summary": "แก้ไขสรุป"}, headers=sureeporn)
    assert len(summaries()) == 1  # editing does not notify again
    cleared = client.patch(f"{API}/notes/{note_id}", json={"issues": ""}, headers=sureeporn)
    assert cleared.json()["issues"] == "" and cleared.json()["summary"] == "แก้ไขสรุป"


def test_note_permissions_and_validation(client, thana, sureeporn, nattawut):
    appt = by_topic(upcoming(client, sureeporn), "ปรึกษาเลือกวิชาเลือกเทอม 2")
    url = f"{API}/appointments/{appt['id']}/notes"
    assert client.post(url, json={"issues": "x"}, headers=thana).status_code == 403
    assert client.post(url, json={"issues": "x"}, headers=nattawut).status_code == 404
    assert client.post(url, json={"issues": "  ", "summary": ""}, headers=sureeporn).status_code == 422
    note_id = client.post(url, json={"issues": "x"}, headers=sureeporn).json()["id"]
    assert client.patch(f"{API}/notes/{note_id}", json={"summary": "y"}, headers=nattawut).status_code == 404


# ---------------------------------------------------------------- tasks

def test_task_lifecycle(client, pimlada, thana, sureeporn):
    appt = by_topic(upcoming(client, sureeporn), "หัวข้อโครงงานจบ")
    created = client.post(
        f"{API}/appointments/{appt['id']}/tasks",
        json={"title": "ส่งร่างโครงงานฉบับแรก", "due_date": (datetime.now(TZ) + timedelta(days=7)).date().isoformat()},
        headers=sureeporn,
    )
    assert created.status_code == 201, created.text
    task = created.json()
    assert task["status"] == "todo" and task["assignee_name"] == "พิมพ์ลดา แก้วมณี" and task["is_overdue"] is False
    assert any(n["type"] == "task" for n in inbox(client, pimlada)["items"])
    assert task["id"] in [t["id"] for t in client.get(f"{API}/tasks", headers=pimlada).json()["items"]]

    assert client.patch(f"{API}/tasks/{task['id']}", json={"status": "doing"}, headers=thana).status_code == 404
    assert client.patch(f"{API}/tasks/{task['id']}", json={"title": "แก้ชื่อ"}, headers=pimlada).status_code == 403
    assert client.patch(f"{API}/tasks/{task['id']}", json={"status": "cancelled"}, headers=pimlada).status_code == 403
    assert client.patch(f"{API}/tasks/{task['id']}", json={"status": "doing"}, headers=pimlada).status_code == 200
    done = client.patch(f"{API}/tasks/{task['id']}", json={"status": "done"}, headers=pimlada)
    assert done.status_code == 200 and done.json()["status"] == "done" and done.json()["completed_at"]
    assert any(n["type"] == "task" and "ทำงานเสร็จแล้ว" in n["title"] for n in inbox(client, sureeporn)["items"])

    reopened = client.patch(f"{API}/tasks/{task['id']}", json={"status": "todo"}, headers=sureeporn)
    assert reopened.json()["completed_at"] is None
    cancelled = client.patch(f"{API}/tasks/{task['id']}", json={"status": "cancelled"}, headers=sureeporn)
    assert cancelled.status_code == 200
    assert task["id"] not in [t["id"] for t in client.get(f"{API}/tasks", headers=pimlada).json()["items"]]


def test_task_listing_flags_overdue_work(client, thana, sureeporn):
    items = client.get(f"{API}/tasks", headers=thana).json()["items"]
    assert len(items) == 3
    overdue = [t for t in items if t["is_overdue"]]
    assert [t["title"] for t in overdue] == ["รวบรวมรายชื่อบริษัทที่รับฝึกงาน 5 แห่ง"]
    assert len(client.get(f"{API}/tasks", params={"status": "done"}, headers=thana).json()["items"]) == 1
    assert len(client.get(f"{API}/tasks", headers=sureeporn).json()["items"]) == 3  # the advisor sees what they assigned
    assert client.get(f"{API}/tasks", params={"status": "bogus"}, headers=thana).status_code == 422


def test_task_validation(client, sureeporn, thana):
    appt = by_topic(upcoming(client, sureeporn), "หัวข้อโครงงานจบ")
    url = f"{API}/appointments/{appt['id']}/tasks"
    assert client.post(url, json={"title": ""}, headers=sureeporn).status_code == 422
    assert client.post(url, json={"title": "x"}, headers=thana).status_code == 403
    foreign_note = "44444444-4444-4444-4444-000000000001"  # belongs to a different appointment
    bad = client.post(url, json={"title": "x", "note_id": foreign_note}, headers=sureeporn)
    assert bad.status_code == 422 and code(bad) == "invalid_note"


# ---------------------------------------------------------------- notifications

def test_notification_inbox(client, thana, pimlada):
    box = inbox(client, thana)
    assert box["unread"] == 1 and len(box["items"]) == 2
    unread = next(n for n in box["items"] if n["read_at"] is None)
    assert client.post(f"{API}/notifications/{unread['id']}/read", headers=pimlada).status_code == 404
    marked = client.post(f"{API}/notifications/{unread['id']}/read", headers=thana)
    assert marked.status_code == 200 and marked.json()["read_at"]
    assert inbox(client, thana)["unread"] == 0
    only_unread = client.get(f"{API}/notifications", params={"unread_only": "true"}, headers=thana).json()
    assert only_unread["items"] == []


def test_read_all(client, sureeporn):
    assert inbox(client, sureeporn)["unread"] == 1
    r = client.post(f"{API}/notifications/read-all", headers=sureeporn)
    assert r.status_code == 200 and r.json() == {"marked": 1}
    assert client.post(f"{API}/notifications/read-all", headers=sureeporn).json() == {"marked": 0}


# ---------------------------------------------------------------- admin

def test_admin_overview_numbers(client, mali):
    r = client.get(f"{API}/admin/overview", headers=mali)
    assert r.status_code == 200, r.text
    o = r.json()
    k = o["kpis"]
    assert (k["slots_total"], k["slots_booked"], k["utilization"]) == (16, 8, 0.5)
    assert (k["appts_completed"], k["appts_no_show"], k["no_show_rate"]) == (4, 1, 0.2)
    assert (k["appts_upcoming"], k["overdue_tasks"]) == (3, 1)
    assert o["departments"] == ["คณิตศาสตร์", "วิศวกรรมคอมพิวเตอร์"]
    assert [(w["full_name"], w["no_shows"], w["overdue_tasks"]) for w in o["watchlist"]] == [("ธนา ศรีสุข", 1, 1)]
    names = {a["full_name"]: a for a in o["advisors"]}
    assert names["อ.สุรีย์พร ใจดี"]["slots_total"] == 10 and names["อ.สุรีย์พร ใจดี"]["utilization"] == 0.5

    math = client.get(f"{API}/admin/overview", params={"department": "คณิตศาสตร์"}, headers=mali).json()
    assert (math["kpis"]["slots_total"], math["kpis"]["slots_booked"], math["kpis"]["appts_no_show"]) == (6, 3, 0)
    assert math["kpis"]["no_show_rate"] == 0.0 and math["kpis"]["overdue_tasks"] == 0 and math["watchlist"] == []


def test_admin_endpoints_are_admin_only(client, thana, sureeporn):
    for who in (thana, sureeporn):
        assert client.get(f"{API}/admin/overview", headers=who).status_code == 403
        assert client.post(f"{API}/admin/jobs/send-reminders", headers=who).status_code == 403
        assert client.put(f"{API}/admin/policy", json={}, headers=who).status_code == 403


def test_policy_roundtrip_and_validation(client, thana, mali):
    default = client.get(f"{API}/policy", headers=thana).json()
    assert default["department"] == "*" and default["max_active_per_student"] == 2
    bad = client.put(f"{API}/admin/policy", json={"min_notice_hours": 12, "cancel_before_hours": 12,
                                                  "max_active_per_student": 0, "reminder_hours_before": 24}, headers=mali)
    assert bad.status_code == 422 and code(bad) == "validation_error"
    set_policy(client, mali, max_active_per_student=3, min_notice_hours=6)
    now = client.get(f"{API}/policy", headers=thana).json()
    assert now["max_active_per_student"] == 3 and now["min_notice_hours"] == 6 and now["updated_by"]
    set_policy(client, mali, department="คณิตศาสตร์", max_active_per_student=1)
    assert client.get(f"{API}/policy", params={"department": "คณิตศาสตร์"}, headers=thana).json()["max_active_per_student"] == 1
    assert client.get(f"{API}/policy", params={"department": "ไม่มีภาคนี้"}, headers=thana).json()["max_active_per_student"] == 3


def test_reminder_job_is_idempotent(client, thana, sureeporn, mali):
    set_policy(client, mali, min_notice_hours=0)  # lets us book something that starts in a few hours
    made = client.post(f"{API}/slots", json={"starts_at": (datetime.now(TZ) + timedelta(hours=3)).isoformat(),
                                             "ends_at": (datetime.now(TZ) + timedelta(hours=3, minutes=30)).isoformat()}, headers=sureeporn)
    assert made.status_code == 201, made.text
    appt = client.post(f"{API}/appointments", json={"slot_id": made.json()["id"], "topic": "ใกล้ถึงเวลา"}, headers=thana).json()
    first = client.post(f"{API}/admin/jobs/send-reminders", headers=mali)
    assert first.status_code == 200 and first.json()["created"] >= 2
    second = client.post(f"{API}/admin/jobs/send-reminders", headers=mali)
    assert second.json() == {"created": 0}
    for who in (thana, sureeporn):
        reminders = [n for n in inbox(client, who)["items"] if n["type"] == "reminder" and n["appointment_id"] == appt["id"]]
        assert len(reminders) == 1


def test_advisor_directory(client, thana):
    items = client.get(f"{API}/advisors", headers=thana).json()["items"]
    assert [a["name"] for a in items] == ["อ.ณัฐวุฒิ รัตนวงศ์", "อ.สุรีย์พร ใจดี"]
    assert len(client.get(f"{API}/advisors", params={"department": "คณิตศาสตร์"}, headers=thana).json()["items"]) == 1


# ------------------------------------------------------------ calendar export

def test_calendar_export_one_and_all(client, thana, sureeporn, mali):
    items = upcoming(client, thana)
    assert items
    r = client.get(f"{API}/appointments/calendar.ics", headers=thana)
    assert r.status_code == 200 and r.headers["content-type"].startswith("text/calendar")
    body = r.content.decode("utf-8")
    assert body.startswith("BEGIN:VCALENDAR\r\n") and body.endswith("END:VCALENDAR\r\n")
    assert body.count("BEGIN:VEVENT") == len(items)
    assert all(len(line.encode("utf-8")) <= 75 for line in body.split("\r\n"))
    one = client.get(f"{API}/appointments/{items[0]['id']}/calendar.ics", headers=thana)
    assert one.status_code == 200 and one.content.decode().count("BEGIN:VEVENT") == 1
    assert f"UID:{items[0]['id']}@advisor-appointment" in one.content.decode()
    # an advisor gets their own appointments, an unrelated user gets 404, admins and anonymous are refused
    assert client.get(f"{API}/appointments/calendar.ics", headers=sureeporn).status_code == 200
    assert client.get(f"{API}/appointments/{items[0]['id']}/calendar.ics", headers=mali).status_code == 403
    assert client.get(f"{API}/appointments/calendar.ics").status_code == 401


def test_ics_escaping_and_folding():
    from datetime import datetime, timezone
    from app.ics import build_calendar
    t = datetime(2030, 1, 2, 3, 4, tzinfo=timezone.utc)
    a = {"id": "x", "status": "confirmed", "topic": "a,b;c\nd\\e " + "ก" * 80, "mode": "online", "location": None,
         "meeting_url": "https://meet.example/x", "starts_at": t, "ends_at": t, "updated_at": t,
         "advisor": {"name": "อ.ทดสอบ"}, "student": {"name": "น.ศ."}}
    body = build_calendar([a], "student").decode("utf-8")
    assert "a\\,b\\;c\\nd\\\\e" in body.replace("\r\n ", "")
    assert all(len(l.encode("utf-8")) <= 75 for l in body.split("\r\n"))
    assert "DTSTART:20300102T030400Z" in body
