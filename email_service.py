"""Email sending for OTP.

Uses SMTP via env vars so we can plug Hostinger email safely.

Required env vars for sending:
- SMTP_HOST (e.g., smtp.hostinger.com)
- SMTP_PORT (465 or 587)
- SMTP_USER (support@knoweasylearning.com)
- SMTP_PASS (mailbox password)
Optional:
- SMTP_SECURITY: "ssl" (465) or "starttls" (587). Default auto by port.
- SMTP_FROM: defaults to SMTP_USER
- SMTP_FROM_NAME: defaults to "KnowEasy"
"""

from __future__ import annotations

import os
import smtplib
from email.message import EmailMessage

def smtp_is_configured() -> bool:
    return bool(os.getenv("SMTP_HOST")) and bool(os.getenv("SMTP_USER")) and bool(os.getenv("SMTP_PASS"))

def _smtp_security(port: int) -> str:
    sec = (os.getenv("SMTP_SECURITY") or "").strip().lower()
    if sec in ("ssl", "starttls"):
        return sec
    # Auto by port
    return "ssl" if port == 465 else "starttls"

def send_otp_email(*, to_email: str, otp: str, role: str) -> None:
    host = (os.getenv("SMTP_HOST") or "").strip()
    port = int(os.getenv("SMTP_PORT") or "465")
    user = (os.getenv("SMTP_USER") or "").strip()
    password = (os.getenv("SMTP_PASS") or "").strip()

    from_email = (os.getenv("SMTP_FROM") or user).strip()
    from_name = (os.getenv("SMTP_FROM_NAME") or "KnowEasy").strip()

    if not host or not user or not password:
        raise RuntimeError("SMTP not configured")

    subject = "Your KnowEasy login code"
    # Keep message short, clear, and consistent.
    body = (
        f"Your KnowEasy login code is: {otp}\n\n"
        f"This code expires in 10 minutes.\n"
        f"If you did not request this code, you can ignore this email.\n\n"
        f"Role: {role.capitalize()}\n"
    )

    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = f"{from_name} <{from_email}>"
    msg["To"] = to_email
    msg.set_content(body)

    security = _smtp_security(port)

    if security == "ssl":
        with smtplib.SMTP_SSL(host, port, timeout=20) as s:
            s.login(user, password)
            s.send_message(msg)
    else:
        with smtplib.SMTP(host, port, timeout=20) as s:
            s.ehlo()
            s.starttls()
            s.ehlo()
            s.login(user, password)
            s.send_message(msg)
