"""Send email through Brevo's HTTPS API (standard library only; no extra package)."""
import json
import logging
import urllib.error
import urllib.request

from . import config

log = logging.getLogger("advisor.mail")
ENDPOINT = "https://api.brevo.com/v3/smtp/email"


def enabled() -> bool:
    return bool(config.BREVO_API_KEY and config.MAIL_FROM_EMAIL and config.APP_URL)


def send(to_email: str, to_name: str, subject: str, text: str) -> bool:
    """True when Brevo accepted the message. Never raises: a mail outage must not break the request."""
    if not enabled():
        return False
    body = json.dumps({
        "sender": {"name": config.MAIL_FROM_NAME, "email": config.MAIL_FROM_EMAIL},
        "to": [{"email": to_email, "name": to_name}],
        "subject": subject,
        "textContent": text,
    }).encode("utf-8")
    req = urllib.request.Request(
        ENDPOINT, data=body, method="POST",
        headers={"api-key": config.BREVO_API_KEY, "content-type": "application/json", "accept": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as res:
            return 200 <= res.status < 300
    except urllib.error.HTTPError as e:
        log.error("Brevo refused the email (HTTP %s): %s", e.code, e.read()[:300])
    except Exception as e:  # network down, timeout, DNS
        log.error("could not reach Brevo: %s", e)
    return False


def send_reset_link(user: dict, token: str) -> bool:
    link = f"{config.APP_URL}/reset-password?token={token}"
    text = (
        f"สวัสดี {user['full_name']}\n\n"
        "มีการขอตั้งรหัสผ่านใหม่สำหรับบัญชีของคุณในระบบนัดหมายอาจารย์\n"
        f"กดลิงก์นี้เพื่อตั้งรหัสผ่านใหม่ (ใช้ได้ภายใน {config.RESET_TOKEN_MINUTES} นาที และใช้ได้ครั้งเดียว):\n\n"
        f"{link}\n\n"
        "ถ้าคุณไม่ได้เป็นผู้ขอ ไม่ต้องทำอะไร รหัสผ่านเดิมยังใช้ได้ตามปกติ และอย่าส่งต่อลิงก์นี้ให้ใคร"
    )
    return send(user["email"], user["full_name"], "ตั้งรหัสผ่านใหม่ - นัดหมายอาจารย์", text)
