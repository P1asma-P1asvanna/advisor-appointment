"""Account management, forced password change, session invalidation, sign-in lockout and the first-admin bootstrap."""
import pytest

pytestmark = pytest.mark.needs_db

API = "/api/v1"
ADMIN = f"{API}/admin/users"


def code(r):
    return r.json()["error"]["code"]


def bearer(token):
    return {"Authorization": "Bearer " + token}


def login(client, email, password="demo1234", **extra):
    return client.post(f"{API}/auth/login", json={"email": email, "password": password, **extra})


def new_user(client, admin, **over):
    body = {"email": "new.student@example.edu", "full_name": "นักศึกษา ใหม่", "role": "student",
            "department": "วิศวกรรมคอมพิวเตอร์", "password": "temp-pass-1", **over}
    return client.post(ADMIN, headers=admin, json=body)


def user_id(client, admin, email):
    items = client.get(ADMIN, headers=admin, params={"q": email}).json()["items"]
    return next(u["id"] for u in items if u["email"] == email)


# ------------------------------------------------------------ create / list

def test_admin_creates_a_user_who_must_pick_a_new_password(client, mali):
    r = new_user(client, mali)
    assert r.status_code == 201, r.text
    u = r.json()
    assert u["email"] == "new.student@example.edu" and u["must_change_password"] is True and u["is_active"] is True
    assert "password_hash" not in u

    s = login(client, "New.Student@example.edu", "temp-pass-1", role="student")
    assert s.status_code == 200 and s.json()["user"]["must_change_password"] is True
    tok = s.json()["access_token"]

    assert client.get(f"{API}/me", headers=bearer(tok)).status_code == 200  # allowed
    blocked = client.get(f"{API}/slots", headers=bearer(tok))
    assert blocked.status_code == 403 and code(blocked) == "password_change_required"

    done = client.post(f"{API}/auth/change-password", headers=bearer(tok),
                       json={"current_password": "temp-pass-1", "new_password": "my-own-pass-9"})
    assert done.status_code == 200 and done.json()["user"]["must_change_password"] is False
    fresh = done.json()["access_token"]
    assert client.get(f"{API}/slots", headers=bearer(fresh)).status_code == 200
    # the token from before the change no longer works
    assert client.get(f"{API}/me", headers=bearer(tok)).status_code == 401
    assert login(client, "new.student@example.edu", "temp-pass-1").status_code == 401
    assert login(client, "new.student@example.edu", "my-own-pass-9").status_code == 200


def test_create_user_validation(client, mali):
    assert code(new_user(client, mali, email="thana@example.edu")) == "email_taken"
    assert new_user(client, mali, department=None).status_code == 422          # students need a department
    assert new_user(client, mali, role="admin", department=None).status_code == 201
    assert new_user(client, mali, email="x@example.edu", password="short").status_code == 422
    assert new_user(client, mali, email="not-an-email").status_code == 422
    assert new_user(client, mali, email="y@example.edu", role="teacher").status_code == 422


def test_only_admins_manage_accounts(client, thana, sureeporn):
    for h in (thana, sureeporn):
        assert client.get(ADMIN, headers=h).status_code == 403
        assert client.post(ADMIN, headers=h, json={}).status_code == 403
    assert client.get(ADMIN).status_code == 401


def test_list_and_filter_users(client, mali):
    items = client.get(ADMIN, headers=mali).json()["items"]
    assert len(items) == 5 and all("password_hash" not in u for u in items)
    advisors = client.get(ADMIN, headers=mali, params={"role": "advisor"}).json()["items"]
    assert sorted(u["email"] for u in advisors) == ["nattawut@example.edu", "sureeporn@example.edu"]
    assert [u["email"] for u in client.get(ADMIN, headers=mali, params={"q": "THANA"}).json()["items"]] == ["thana@example.edu"]
    assert client.get(ADMIN, headers=mali, params={"role": "boss"}).status_code == 422
    assert client.get(ADMIN, headers=mali, params={"active": "false"}).json()["items"] == []


# ------------------------------------------------------------ update / deactivate

def test_update_name_and_department(client, mali):
    uid = user_id(client, mali, "thana@example.edu")
    r = client.patch(f"{ADMIN}/{uid}", headers=mali, json={"full_name": "ธนา ศรีสุข (ปรับ)", "department": "คณิตศาสตร์"})
    assert r.status_code == 200 and r.json()["full_name"].endswith("(ปรับ)") and r.json()["department"] == "คณิตศาสตร์"
    assert client.patch(f"{ADMIN}/{uid}", headers=mali, json={"department": "  "}).status_code == 422  # a student needs one
    assert client.patch(f"{ADMIN}/{uid}", headers=mali, json={}).status_code == 422
    missing = client.patch(f"{ADMIN}/00000000-0000-0000-0000-00000000dead", headers=mali, json={"full_name": "x"})
    assert missing.status_code == 404 and code(missing) == "user_not_found"


def test_deactivating_an_advisor_closes_their_open_slots_and_ends_their_sessions(client, mali, nattawut, thana):
    before = client.get(f"{API}/slots", headers=thana).json()["items"]
    assert any(s["advisor"]["name"].startswith("อ.ณัฐวุฒิ") for s in before)
    uid = user_id(client, mali, "nattawut@example.edu")

    r = client.patch(f"{ADMIN}/{uid}", headers=mali, json={"is_active": False})
    assert r.status_code == 200 and r.json()["is_active"] is False

    after = client.get(f"{API}/slots", headers=thana).json()["items"]
    assert not any(s["advisor"]["name"].startswith("อ.ณัฐวุฒิ") for s in after)
    assert "อ.ณัฐวุฒิ" not in str(client.get(f"{API}/advisors", headers=thana).json())
    assert client.get(f"{API}/me", headers=nattawut).status_code == 401           # existing session is over
    off = login(client, "nattawut@example.edu")
    assert off.status_code == 403 and code(off) == "account_disabled"

    back = client.patch(f"{ADMIN}/{uid}", headers=mali, json={"is_active": True})
    assert back.status_code == 200 and login(client, "nattawut@example.edu").status_code == 200
    # the slots that were closed stay closed: the advisor opens new ones
    assert not any(s["advisor"]["name"].startswith("อ.ณัฐวุฒิ") for s in client.get(f"{API}/slots", headers=thana).json()["items"])


def test_an_admin_cannot_switch_themselves_off_or_reset_their_own_password(client, mali):
    me = user_id(client, mali, "mali@example.edu")
    r = client.patch(f"{ADMIN}/{me}", headers=mali, json={"is_active": False})
    assert r.status_code == 409 and code(r) == "cannot_modify_self"
    r = client.post(f"{ADMIN}/{me}/reset-password", headers=mali, json={"password": "another-pass-1"})
    assert r.status_code == 409 and code(r) == "cannot_modify_self"


# ------------------------------------------------------------ reset password

def test_reset_password_ends_old_sessions_and_forces_a_change(client, mali, thana):
    uid = user_id(client, mali, "thana@example.edu")
    assert client.post(f"{ADMIN}/{uid}/reset-password", headers=mali, json={"password": "short"}).status_code == 422
    assert client.post(f"{ADMIN}/{uid}/reset-password", headers=mali, json={"password": "temp-reset-1"}).json() == {"ok": True}

    assert client.get(f"{API}/me", headers=thana).status_code == 401
    assert login(client, "thana@example.edu", "demo1234").status_code == 401
    s = login(client, "thana@example.edu", "temp-reset-1")
    assert s.status_code == 200 and s.json()["user"]["must_change_password"] is True


# ------------------------------------------------------------ change my own password

def test_change_password_rules(client, thana):
    bad = client.post(f"{API}/auth/change-password", headers=thana, json={"current_password": "wrong-one", "new_password": "brand-new-pass"})
    assert bad.status_code == 403 and code(bad) == "wrong_password"
    same = client.post(f"{API}/auth/change-password", headers=thana, json={"current_password": "demo1234", "new_password": "demo1234"})
    assert same.status_code == 422
    short = client.post(f"{API}/auth/change-password", headers=thana, json={"current_password": "demo1234", "new_password": "abc"})
    assert short.status_code == 422
    assert client.post(f"{API}/auth/change-password", json={"current_password": "a", "new_password": "bbbbbbbb"}).status_code == 401


# ------------------------------------------------------------ sign-in lockout

def test_too_many_wrong_passwords_lock_the_email(client):
    for _ in range(5):
        assert code(login(client, "thana@example.edu", "nope")) == "invalid_credentials"
    locked = login(client, "thana@example.edu", "demo1234")           # even the right password is refused now
    assert locked.status_code == 429 and code(locked) == "too_many_attempts"
    assert locked.json()["error"]["details"]["retry_after_minutes"] >= 1
    assert login(client, "pimlada@example.edu").status_code == 200    # other people are not affected


def test_unknown_emails_are_throttled_the_same_way(client):
    for _ in range(5):
        assert login(client, "ghost@example.edu", "nope").status_code == 401
    assert code(login(client, "ghost@example.edu", "nope")) == "too_many_attempts"


def test_a_good_login_resets_the_counter(client):
    for _ in range(4):
        login(client, "thana@example.edu", "nope")
    assert login(client, "thana@example.edu").status_code == 200
    for _ in range(4):
        login(client, "thana@example.edu", "nope")
    assert login(client, "thana@example.edu").status_code == 200       # would be locked if the counter had not been reset


def test_admin_reset_lifts_a_lockout(client, mali):
    for _ in range(5):
        login(client, "thana@example.edu", "nope")
    assert code(login(client, "thana@example.edu")) == "too_many_attempts"
    uid = user_id(client, mali, "thana@example.edu")
    client.post(f"{ADMIN}/{uid}/reset-password", headers=mali, json={"password": "temp-reset-1"})
    assert login(client, "thana@example.edu", "temp-reset-1").status_code == 200


def test_guessing_the_current_password_is_throttled_too(client, thana):
    for _ in range(5):
        r = client.post(f"{API}/auth/change-password", headers=thana, json={"current_password": "x" * 9, "new_password": "brand-new-pass"})
        assert code(r) == "wrong_password"
    r = client.post(f"{API}/auth/change-password", headers=thana, json={"current_password": "demo1234", "new_password": "brand-new-pass"})
    assert r.status_code == 429


# ------------------------------------------------------------ first admin

def test_bootstrap_admin_is_created_once_and_only_on_an_empty_admin_table(client, monkeypatch):
    from app import bootstrap, config
    from app.db import connection

    monkeypatch.setattr(config, "BOOTSTRAP_ADMIN_EMAIL", "first.admin@example.edu")
    monkeypatch.setattr(config, "BOOTSTRAP_ADMIN_PASSWORD", "first-admin-pass")
    monkeypatch.setattr(config, "BOOTSTRAP_ADMIN_NAME", "ผู้ดูแลคนแรก")

    with connection() as conn:
        assert bootstrap.ensure_admin(conn) is False                      # an admin (มาลี) already exists
        conn.execute("DELETE FROM notifications WHERE user_id IN (SELECT id FROM users WHERE role = 'admin')")
        conn.execute("DELETE FROM users WHERE role = 'admin'")
        assert bootstrap.ensure_admin(conn) is True
        assert bootstrap.ensure_admin(conn) is False                      # now it exists again

    s = login(client, "first.admin@example.edu", "first-admin-pass", role="admin")
    assert s.status_code == 200 and s.json()["user"]["must_change_password"] is True
    assert s.json()["user"]["full_name"] == "ผู้ดูแลคนแรก"
    assert client.get(ADMIN, headers=bearer(s.json()["access_token"])).status_code == 403  # until the password is changed


def test_bootstrap_does_nothing_without_settings(client, monkeypatch):
    from app import bootstrap, config
    from app.db import connection

    monkeypatch.setattr(config, "BOOTSTRAP_ADMIN_EMAIL", "")
    with connection() as conn:
        conn.execute("DELETE FROM notifications WHERE user_id IN (SELECT id FROM users WHERE role = 'admin')")
        conn.execute("DELETE FROM users WHERE role = 'admin'")
        assert bootstrap.ensure_admin(conn) is False
        assert conn.execute("SELECT count(*) AS n FROM users WHERE role = 'admin'").fetchone()["n"] == 0


# ------------------------------------------------------------ editing

def test_admin_fixes_email_and_role_and_the_person_is_signed_out(client, mali):
    assert new_user(client, mali, email="typo@example.edu").status_code == 201
    old = login(client, "typo@example.edu", "temp-pass-1")
    assert old.status_code == 200
    uid = user_id(client, mali, "typo@example.edu")
    r = client.patch(f"{ADMIN}/{uid}", headers=mali, json={"email": " Right@Example.edu ", "role": "advisor"})
    assert r.status_code == 200, r.text
    assert r.json()["email"] == "right@example.edu" and r.json()["role"] == "advisor"
    # the old session stops working and the old email no longer signs in
    assert client.get(f"{API}/me", headers=bearer(old.json()["access_token"])).status_code == 401
    assert login(client, "typo@example.edu", "temp-pass-1").status_code == 401
    assert login(client, "right@example.edu", "temp-pass-1", role="advisor").status_code == 200


def test_email_and_role_edits_are_guarded(client, mali, thana):
    uid = user_id(client, mali, "thana@example.edu")
    r = client.patch(f"{ADMIN}/{uid}", headers=mali, json={"role": "advisor"})
    assert r.status_code == 409 and code(r) == "role_in_use"          # he still has a live appointment
    taken = client.patch(f"{ADMIN}/{uid}", headers=mali, json={"email": "pimlada@example.edu"})
    assert taken.status_code == 409 and code(taken) == "email_taken"
    assert client.patch(f"{ADMIN}/{uid}", headers=mali, json={"email": "not-an-email"}).status_code == 422
    me = user_id(client, mali, "mali@example.edu")
    own = client.patch(f"{ADMIN}/{me}", headers=mali, json={"role": "student"})
    assert own.status_code == 409 and code(own) == "cannot_modify_self"
    assert client.patch(f"{ADMIN}/{uid}", headers=thana, json={"email": "x@example.edu"}).status_code == 403
    # an admin without a department may become an advisor only with one
    assert new_user(client, mali, email="staff@example.edu", role="admin", department=None).status_code == 201
    sid = user_id(client, mali, "staff@example.edu")
    need = client.patch(f"{ADMIN}/{sid}", headers=mali, json={"role": "advisor"})
    assert need.status_code == 422 and code(need) == "department_required"
    ok = client.patch(f"{ADMIN}/{sid}", headers=mali, json={"role": "advisor", "department": "คณิตศาสตร์"})
    assert ok.status_code == 200 and ok.json()["role"] == "advisor"


def test_anyone_can_fix_their_own_name_only(client, thana):
    r = client.patch(f"{API}/me", headers=thana, json={"full_name": "  ธนา ศรีสุข (แก้)  "})
    assert r.status_code == 200 and r.json()["full_name"] == "ธนา ศรีสุข (แก้)"
    assert client.get(f"{API}/me", headers=thana).json()["full_name"] == "ธนา ศรีสุข (แก้)"
    assert client.patch(f"{API}/me", headers=thana, json={"full_name": " "}).status_code == 422
    r = client.patch(f"{API}/me", headers=thana, json={"full_name": "ธนา", "role": "admin", "email": "a@b.co"})
    assert r.status_code == 200 and r.json()["role"] == "student" and r.json()["email"] == "thana@example.edu"


# ------------------------------------------------------------ forgot password by email

@pytest.fixture
def outbox(monkeypatch):
    """Turn email on and capture what would be sent."""
    from app import config, mailer
    monkeypatch.setattr(config, "BREVO_API_KEY", "test-key")
    monkeypatch.setattr(config, "MAIL_FROM_EMAIL", "noreply@example.edu")
    monkeypatch.setattr(config, "APP_URL", "https://app.example.edu")
    sent = []
    monkeypatch.setattr(mailer, "send", lambda to, name, subject, text: sent.append((to, text)) or True)
    return sent


def _token(text):
    return text.split("token=")[1].split()[0]


def test_features_reports_whether_email_is_set_up(client, outbox, monkeypatch):
    assert client.get(f"{API}/auth/features").json() == {"password_reset": True}
    from app import config
    monkeypatch.setattr(config, "BREVO_API_KEY", "")
    assert client.get(f"{API}/auth/features").json() == {"password_reset": False}


def test_forgot_password_email_roundtrip(client, outbox):
    r = client.post(f"{API}/auth/forgot-password", json={"email": " Thana@Example.edu "})
    assert r.status_code == 200 and r.json() == {"ok": True}
    assert len(outbox) == 1 and outbox[0][0] == "thana@example.edu"
    assert outbox[0][1].count("https://app.example.edu/reset-password?token=") == 1
    token = _token(outbox[0][1])
    old = login(client, "thana@example.edu")
    assert old.status_code == 200
    assert client.post(f"{API}/auth/reset-password", json={"token": token, "new_password": "short"}).status_code == 422
    ok = client.post(f"{API}/auth/reset-password", json={"token": token, "new_password": "brand-new-pass"})
    assert ok.status_code == 200
    assert login(client, "thana@example.edu").status_code == 401                         # old password gone
    fresh = login(client, "thana@example.edu", "brand-new-pass")
    assert fresh.status_code == 200 and fresh.json()["user"]["must_change_password"] is False
    assert client.get(f"{API}/me", headers=bearer(old.json()["access_token"])).status_code == 401  # old sessions end
    again = client.post(f"{API}/auth/reset-password", json={"token": token, "new_password": "another-pass-1"})
    assert again.status_code == 400 and code(again) == "invalid_or_expired_token"       # single use


def test_forgot_password_never_reveals_which_emails_exist(client, outbox):
    known = client.post(f"{API}/auth/forgot-password", json={"email": "thana@example.edu"})
    unknown = client.post(f"{API}/auth/forgot-password", json={"email": "nobody@example.edu"})
    assert known.status_code == unknown.status_code == 200 and known.json() == unknown.json()
    assert [to for to, _ in outbox] == ["thana@example.edu"]


def test_forgot_password_skips_disabled_accounts_and_limits_requests(client, mali, outbox):
    uid = user_id(client, mali, "pimlada@example.edu")
    assert client.patch(f"{ADMIN}/{uid}", headers=mali, json={"is_active": False}).status_code == 200
    client.post(f"{API}/auth/forgot-password", json={"email": "pimlada@example.edu"})
    assert outbox == []
    for _ in range(5):
        client.post(f"{API}/auth/forgot-password", json={"email": "thana@example.edu"})
    assert len(outbox) == 3                                                              # RESET_MAX_PER_HOUR


def test_a_new_link_replaces_the_old_one_and_links_expire(client, outbox):
    from tests.conftest import _run_script
    client.post(f"{API}/auth/forgot-password", json={"email": "thana@example.edu"})
    client.post(f"{API}/auth/forgot-password", json={"email": "thana@example.edu"})
    first, second = _token(outbox[0][1]), _token(outbox[1][1])
    assert client.post(f"{API}/auth/reset-password", json={"token": first, "new_password": "brand-new-pass"}).status_code == 400
    _run_script("UPDATE password_resets SET expires_at = now() - interval '1 minute'")
    late = client.post(f"{API}/auth/reset-password", json={"token": second, "new_password": "brand-new-pass"})
    assert late.status_code == 400 and code(late) == "invalid_or_expired_token"
    assert client.post(f"{API}/auth/reset-password", json={"token": "x" * 30, "new_password": "brand-new-pass"}).status_code == 400


def test_forgot_password_does_nothing_when_email_is_not_configured(client):
    assert client.post(f"{API}/auth/forgot-password", json={"email": "thana@example.edu"}).json() == {"ok": True}


def test_stored_reset_tokens_are_hashed(client, outbox):
    from tests.conftest import _run_script  # noqa: F401
    client.post(f"{API}/auth/forgot-password", json={"email": "thana@example.edu"})
    token = _token(outbox[0][1])
    import psycopg, os
    with psycopg.connect(os.environ["TEST_DATABASE_URL"]) as c:
        stored = [(next(iter(r.values())) if isinstance(r, dict) else r[0]) for r in c.execute("SELECT token_hash FROM password_resets").fetchall()]
    assert stored and token not in stored and all(len(h) == 64 for h in stored)


# ------------------------------------------------------------ audit trail

def test_admin_changes_are_recorded_without_secrets(client, mali):
    assert new_user(client, mali, email="audit.me@example.edu").status_code == 201
    uid = user_id(client, mali, "audit.me@example.edu")
    client.patch(f"{ADMIN}/{uid}", headers=mali, json={"full_name": "ชื่อใหม่", "email": "audit.new@example.edu"})
    client.post(f"{ADMIN}/{uid}/reset-password", headers=mali, json={"password": "secret-temp-1"})
    client.put(f"{API}/admin/policy", headers=mali, json={"department": "*", "min_notice_hours": 5, "cancel_before_hours": 6,
                                                         "max_active_per_student": 3, "reminder_hours_before": 20})
    items = client.get(f"{API}/admin/audit", headers=mali).json()["items"]
    actions = [i["action"] for i in items]
    assert actions[:4] == ["policy.update", "user.reset_password", "user.update", "user.create"]
    upd = next(i for i in items if i["action"] == "user.update")
    assert upd["actor_email"] == "mali@example.edu" and upd["target_email"] == "audit.new@example.edu"
    assert upd["details"]["email"] == {"from": "audit.me@example.edu", "to": "audit.new@example.edu"}
    assert "secret-temp-1" not in str(items) and "temp-pass-1" not in str(items)
    found = client.get(f"{API}/admin/audit", headers=mali, params={"q": "audit.new"}).json()["items"]
    assert found and all("audit.new" in (i["target_email"] or "") for i in found)
    # nothing is recorded when nothing changed
    n = len(items)
    client.patch(f"{ADMIN}/{uid}", headers=mali, json={"full_name": "ชื่อใหม่"})
    assert len(client.get(f"{API}/admin/audit", headers=mali).json()["items"]) == n


def test_only_admins_read_the_audit_trail(client, thana, sureeporn):
    assert client.get(f"{API}/admin/audit", headers=thana).status_code == 403
    assert client.get(f"{API}/admin/audit", headers=sureeporn).status_code == 403
    assert client.get(f"{API}/admin/audit").status_code == 401


# ------------------------------------------------------------ department pick-list

def test_department_list_and_validation(client, mali, thana):
    groups = client.get(f"{API}/departments", headers=thana).json()["groups"]
    names = [d for g in groups for d in g["departments"]]
    assert "วิศวกรรมคอมพิวเตอร์" in names and "คณิตศาสตร์" in names and "สำนักงานคณะ" in names
    assert len(names) == len(set(names)) and client.get(f"{API}/departments").status_code == 401
    bad = new_user(client, mali, email="free.text@example.edu", department="ภาควิชาที่พิมพ์เอง")
    assert bad.status_code == 422 and code(bad) == "invalid_department"
    assert new_user(client, mali, email="listed@example.edu", department="สถิติ").status_code == 201
    uid = user_id(client, mali, "listed@example.edu")
    r = client.patch(f"{ADMIN}/{uid}", headers=mali, json={"department": "พิมพ์เอง"})
    assert r.status_code == 422 and code(r) == "invalid_department"
    assert client.patch(f"{ADMIN}/{uid}", headers=mali, json={"department": "ฟิสิกส์"}).json()["department"] == "ฟิสิกส์"


def test_a_department_no_longer_in_the_list_still_works_when_left_unchanged(client, mali):
    from tests.conftest import _run_script
    assert new_user(client, mali, email="legacy@example.edu").status_code == 201
    _run_script("UPDATE users SET department = 'ชื่อเก่าที่เลิกใช้' WHERE email = 'legacy@example.edu'")
    uid = user_id(client, mali, "legacy@example.edu")
    ok = client.patch(f"{ADMIN}/{uid}", headers=mali, json={"full_name": "แก้ชื่ออย่างเดียว", "department": "ชื่อเก่าที่เลิกใช้"})
    assert ok.status_code == 200 and ok.json()["department"] == "ชื่อเก่าที่เลิกใช้"
