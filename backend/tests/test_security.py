"""No database needed."""
import time
from uuid import uuid4

import jwt
import pytest

from app import config
from app.errors import RULES, map_db_error
from app.schemas import NotePatch, PolicyIn, SlotIn, TaskPatch
from app.security import create_token, decode_token, hash_password, verify_password


def test_password_roundtrip():
    h = hash_password("correct horse")
    assert h.startswith("scrypt$")
    assert verify_password("correct horse", h)
    assert not verify_password("wrong", h)
    assert hash_password("correct horse") != h  # random salt


def test_password_rejects_malformed_hashes():
    for bad in ("", "nonsense", "bcrypt$1$2$3$4$5", "scrypt$x$y$z$a$b"):
        assert not verify_password("x", bad)


def test_token_roundtrip_and_tamper():
    uid = uuid4()
    token = create_token(uid, "student")
    claims = decode_token(token)
    assert claims["sub"] == str(uid) and claims["role"] == "student"
    with pytest.raises(jwt.PyJWTError):
        decode_token(token[:-2] + ("AA" if token[-2:] != "AA" else "BB"))


def test_expired_token_rejected():
    now = int(time.time())
    token = jwt.encode({"sub": str(uuid4()), "exp": now - 10}, config.JWT_SECRET, algorithm=config.JWT_ALGORITHM)
    with pytest.raises(jwt.ExpiredSignatureError):
        decode_token(token)


def test_token_without_expiry_rejected():
    token = jwt.encode({"sub": str(uuid4())}, config.JWT_SECRET, algorithm=config.JWT_ALGORITHM)
    with pytest.raises(jwt.PyJWTError):
        decode_token(token)


class _Diag:
    def __init__(self, message_primary=None, constraint_name=None):
        self.message_primary = message_primary
        self.constraint_name = constraint_name


class _Err(Exception):
    def __init__(self, sqlstate, message=None, constraint=None):
        super().__init__(message or "")
        self.sqlstate = sqlstate
        self.diag = _Diag(message, constraint)


def test_every_rule_maps_to_its_status():
    for code, (status, _msg) in RULES.items():
        mapped = map_db_error(_Err("P0001", code))
        assert mapped is not None and mapped.code == code and mapped.status == status


def test_database_constraint_errors_map():
    assert map_db_error(_Err("23P01")).code == "slot_overlaps"
    assert map_db_error(_Err("23505", constraint="uq_active_appointment_per_slot")).code == "slot_unavailable"
    assert map_db_error(_Err("23505")).code == "already_exists"
    assert map_db_error(_Err("23503")).status == 422
    assert map_db_error(_Err("22P02")).code == "invalid_value"


def test_unknown_database_errors_are_not_mapped():
    assert map_db_error(_Err("P0001", "something_else")) is None
    assert map_db_error(_Err("XX000", "boom")) is None


def test_slot_duration_limits():
    ok = SlotIn(starts_at="2030-01-01T10:00:00+07:00", ends_at="2030-01-01T10:30:00+07:00")
    assert ok.mode == "onsite"
    with pytest.raises(ValueError):
        SlotIn(starts_at="2030-01-01T10:00:00+07:00", ends_at="2030-01-01T10:05:00+07:00")
    with pytest.raises(ValueError):
        SlotIn(starts_at="2030-01-01T10:00:00", ends_at="2030-01-01T10:30:00")  # no time zone


def test_patch_bodies_need_something_to_change():
    with pytest.raises(ValueError):
        NotePatch()
    with pytest.raises(ValueError):
        TaskPatch()
    assert NotePatch(summary="").summary == ""  # an empty string is a real value: it clears the field


def test_policy_bounds():
    PolicyIn(min_notice_hours=0, cancel_before_hours=0, max_active_per_student=1, reminder_hours_before=1)
    with pytest.raises(ValueError):
        PolicyIn(min_notice_hours=0, cancel_before_hours=0, max_active_per_student=0, reminder_hours_before=1)


def test_user_input_rules():
    from app.schemas import ChangePasswordIn, UserIn

    ok = UserIn(email=" Someone@Example.EDU ", full_name="ชื่อ", role="student", department="วิศวกรรมคอมพิวเตอร์", password="12345678")
    assert ok.email == "someone@example.edu"
    assert UserIn(email="a@b.co", full_name="ผู้ดูแล", role="admin", password="12345678", department="  ").department is None
    for bad in (
        dict(role="advisor", department=None),                  # needs a department
        dict(role="student", department="x", password="short"),
        dict(role="student", department="x", email="no-at-sign"),
        dict(role="hacker", department="x"),
    ):
        base = dict(email="a@b.co", full_name="x", role="student", department="x", password="12345678")
        with pytest.raises(ValueError):
            UserIn(**{**base, **bad})
    with pytest.raises(ValueError):
        ChangePasswordIn(current_password="same-pass-1", new_password="same-pass-1")


def test_token_issued_after_a_moment_is_newer_than_it():
    import time as _t

    before = _t.time()
    claims = decode_token(create_token(uuid4(), "student"))
    assert claims["iat"] >= before


def test_temp_password_shape_and_cheaper_hash_still_verifies():
    from app.security import temp_password

    pw = temp_password()
    assert len(pw) == 14 and pw.count("-") == 2 and pw == pw.lower()
    assert not set(pw.replace("-", "")) & set("01oli")
    assert temp_password() != pw
    h = hash_password(pw, 2**12)
    assert h.startswith("scrypt$4096$") and verify_password(pw, h) and not verify_password(pw + "x", h)
