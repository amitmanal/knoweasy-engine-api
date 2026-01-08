"""Email sending for OTP.

This module supports two delivery modes:
1) SMTP (traditional) - good for local/dev or paid hosting that allows SMTP outbound.
2) Resend (HTTPS API) - works on platforms that block SMTP outbound (e.g., Render Free tier).

Environment variables (SMTP):
- SMTP_HOST (e.g., smtp.hostinger.com)
- SMTP_PORT (465, 587, etc)
- SMTP_USER (full email address)
- SMTP_PASS (mailbox password)
- SMTP_FROM (from email address)
- SMTP_FROM_NAME (display name, optional)
- SMTP_SECURITY: "ssl" or "tls" (optional; inferred from port if missing)

Environment variables (Resend):
- EMAIL_PROVIDER="resend" (or "auto")
- RESEND_API_KEY (required for Resend)
- RESEND_FROM (optional; defaults to SMTP_FROM)
- RESEND_FROM_NAME (optional; defaults to SMTP_FROM_NAME)

Provider selection:
- EMAIL_PROVIDER="smtp"   -> SMTP only
- EMAIL_PROVIDER="resend" -> Resend only
- EMAIL_PROVIDER="auto"   -> try SMTP, then Resend if SMTP fails
"""

from __future__ import annotations

import os
import smtplib
import socket
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Optional

import logging

logger = logging.getLogger("knoweasy.email")

try:
    import requests  # type: ignore
except Exception:  # pragma: no cover
    requests = None  # type: ignore


def _get_env(key: str, default: Optional[str] = None) -> Optional[str]:
    val = os.getenv(key)
    return val if val not in (None, "") else default


def _smtp_security(host: str, port: int) -> str:
    # Default inference:
    # - 465: implicit SSL
    # - 587: STARTTLS
    sec = (_get_env("SMTP_SECURITY", "") or "").strip().lower()
    if sec in ("ssl", "tls"):
        return sec
    if port == 465:
        return "ssl"
    return "tls"


def _send_via_smtp(to_email: str, subject: str, body_text: str) -> None:
    host = _get_env("SMTP_HOST")
    port_str = _get_env("SMTP_PORT")
    user = _get_env("SMTP_USER")
    password = _get_env("SMTP_PASS")
    from_email = _get_env("SMTP_FROM", user)
    from_name = _get_env("SMTP_FROM_NAME", "KnowEasy")

    if not host or not port_str or not user or not password or not from_email:
        raise RuntimeError(
            "SMTP is not fully configured. Required: SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASS, SMTP_FROM."
        )

    try:
        port = int(port_str)
    except ValueError as e:
        raise RuntimeError("SMTP_PORT must be an integer.") from e

    msg = MIMEMultipart()
    msg["From"] = f"{from_name} <{from_email}>"
    msg["To"] = to_email
    msg["Subject"] = subject
    msg.attach(MIMEText(body_text, "plain", "utf-8"))

    security = _smtp_security(host, port)
    logger.info("Sending OTP email via SMTP (%s:%s, security=%s) to=%s", host, port, security, to_email)

    if security == "ssl":
        server = smtplib.SMTP_SSL(host, port, timeout=20)
    else:
        server = smtplib.SMTP(host, port, timeout=20)

    try:
        server.ehlo()
        if security == "tls":
            server.starttls()
            server.ehlo()
        server.login(user, password)
        server.sendmail(from_email, [to_email], msg.as_string())
    finally:
        try:
            server.quit()
        except Exception:
            pass


def _send_via_resend(to_email: str, subject: str, body_text: str) -> None:
    api_key = _get_env("RESEND_API_KEY")
    if not api_key:
        raise RuntimeError("RESEND_API_KEY is missing (cannot send via Resend).")

    if requests is None:
        raise RuntimeError("Python package 'requests' is missing; add it to requirements.txt.")

    from_email = _get_env("RESEND_FROM") or _get_env("SMTP_FROM") or _get_env("SMTP_USER")
    from_name = _get_env("RESEND_FROM_NAME") or _get_env("SMTP_FROM_NAME") or "KnowEasy"

    if not from_email:
        raise RuntimeError("RESEND_FROM (or SMTP_FROM) is missing.")

    # Resend allows "Name <email>" format.
    from_field = f"{from_name} <{from_email}>"

    logger.info("Sending OTP email via Resend to=%s from=%s", to_email, from_email)

    resp = requests.post(
        "https://api.resend.com/emails",
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        json={
            "from": from_field,
            "to": [to_email],
            "subject": subject,
            "text": body_text,
            "reply_to": from_email,
        },
        timeout=20,
    )
    if resp.status_code >= 400:
        # Avoid logging full response body if it might contain hints, but include first 400 chars for debugging.
        snippet = (resp.text or "")[:400]
        raise RuntimeError(f"Resend API error {resp.status_code}: {snippet}")


def send_otp_email(to_email: str, otp: str, role: str) -> None:
    """Send OTP email for login."""
    subject = "Your KnowEasy login code"
    body = (
        f"Your KnowEasy login code is: {otp}

"
        "This code expires in 10 minutes.

"
        f"Role: {role}
"
        "If you did not request this, you can ignore this email."
    )

    provider = (_get_env("EMAIL_PROVIDER", "auto") or "auto").strip().lower()

    last_err: Optional[Exception] = None

    if provider in ("smtp", "auto"):
        try:
            _send_via_smtp(to_email=to_email, subject=subject, body_text=body)
            return
        except Exception as e:
            last_err = e
            # On Render free tier, SMTP ports are blocked -> often socket.gaierror / OSError 101.
            logger.exception("SMTP send failed (provider=%s).", provider)

            if provider == "smtp":
                raise

    if provider in ("resend", "auto"):
        try:
            _send_via_resend(to_email=to_email, subject=subject, body_text=body)
            return
        except Exception as e:
            last_err = e
            logger.exception("Resend send failed (provider=%s).", provider)
            raise

    # If we reach here, nothing worked.
    raise RuntimeError("Failed to send OTP email.") from last_err
