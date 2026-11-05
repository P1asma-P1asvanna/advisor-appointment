"""Password hashing (scrypt from the standard library) and JWT helpers.

Create a hash for a manually inserted user:   python -m app.security 'the-password'
"""
import base64
import hashlib
import hmac
import os
import sys
import time
from uuid import UUID

import jwt

from . import config

_N, _R, _P = 2**14, 8, 1  # ~16 MiB of memory per hash, about 50 ms


def _b64(b: bytes) -> str:
    return base64.b64encode(b).decode("ascii")


def _unb64(s: str) -> bytes:
    return base64.b64decode(s.encode("ascii"))


def hash_password(password: str, n: int = _N) -> str:
    """`n` is the scrypt cost. Bulk imports use a smaller one for their long random temporary passwords, which
    the person replaces at first sign-in. The cost is stored in the hash, so verify_password needs no change."""
    salt = os.urandom(16)
    dk = hashlib.scrypt(password.encode("utf-8"), salt=salt, n=n, r=_R, p=_P, dklen=32)
    return f"scrypt${n}${_R}${_P}${_b64(salt)}${_b64(dk)}"


_TEMP_ALPHABET = "abcdefghjkmnpqrstuvwxyz23456789"  # no 0/o/1/l/i: easy to read out loud and to type


def temp_password() -> str:
    """A random temporary password such as 'k7mq-x2pn-9tfa' (12 characters, about 59 bits)."""
    import secrets

    return "-".join("".join(secrets.choice(_TEMP_ALPHABET) for _ in range(4)) for _ in range(3))


def verify_password(password: str, stored: str) -> bool:
    try:
        scheme, n, r, p, salt, expected = stored.split("$")
        if scheme != "scrypt":
            return False
        want = _unb64(expected)
        got = hashlib.scrypt(password.encode("utf-8"), salt=_unb64(salt), n=int(n), r=int(r), p=int(p), dklen=len(want))
    except (ValueError, TypeError):
        return False
    return hmac.compare_digest(got, want)


# Verified against when the email is unknown, so "no such user" and "wrong password" take the same time.
DUMMY_HASH = hash_password("not-a-real-password")


def create_token(user_id: UUID, role: str) -> str:
    now = time.time()  # fractional, so a token issued right after a password change is newer than the change
    payload = {"sub": str(user_id), "role": role, "iat": now, "exp": int(now) + config.JWT_TTL_MINUTES * 60}
    return jwt.encode(payload, config.JWT_SECRET, algorithm=config.JWT_ALGORITHM)


def decode_token(token: str) -> dict:
    """Raises jwt.PyJWTError when the token is malformed, tampered with or expired."""
    return jwt.decode(
        token, config.JWT_SECRET, algorithms=[config.JWT_ALGORITHM], options={"require": ["exp", "sub"]}
    )


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit("usage: python -m app.security 'password'")
    print(hash_password(sys.argv[1]))
