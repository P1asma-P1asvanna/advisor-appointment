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
    assert client.patch(f"{ADMIN}/{uid}", headers=mali, json={"role": "admin"}).status_code == 422      # the role is fixed
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
