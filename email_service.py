"""Email sending utilities.

Supports:
- SMTP (Hostinger or any SMTP server)
- Resend (API) for scalable transactional email

Decision order:
1) If EMAIL_PROVIDER=resend and RESEND_API_KEY is set -> Resend
2) If EMAIL_PROVIDER=smtp and SMTP_* configured -> SMTP
3) Fallback: prefer Resend if configured, else SMTP

This file is intentionally dependency-light (uses stdlib only).
"""

from __future__ import annotations

import json
import os
import smtplib
import ssl
from email.message import EmailMessage
from typing import Optional, Tuple
from urllib import request, error


def _env(name: str, default: str = "") -> str:
    v = os.getenv(name)
    return (v if v is not None else default).strip()


# Generic "from" settings (recommended)
EMAIL_FROM = _env("EMAIL_FROM") or _env("SMTP_FROM")  # allow legacy SMTP_FROM
SMTP_FROM_NAME = _env("SMTP_FROM_NAME", "KnowEasy")

# SMTP settings
SMTP_HOST = _env("SMTP_HOST")
SMTP_PORT = int(_env("SMTP_PORT", "587") or "587")
SMTP_USER = _env("SMTP_USER")
SMTP_PASS = _env("SMTP_PASS")
SMTP_SECURITY = _env("SMTP_SECURITY", "starttls").lower()  # starttls | ssl

# Resend settings
RESEND_API_KEY = _env("RESEND_API_KEY")
EMAIL_REGION = _env("EMAIL_REGION")  # optional; kept for compatibility
RESEND_ENDPOINT = "https://api.resend.com/emails"

# Provider selector
EMAIL_PROVIDER = (_env("EMAIL_PROVIDER") or "").lower()  # resend | smtp | ""


def smtp_is_configured() -> bool:
    return all([SMTP_HOST, SMTP_USER, SMTP_PASS, EMAIL_FROM])


def resend_is_configured() -> bool:
    return bool(RESEND_API_KEY and EMAIL_FROM)


def _choose_provider() -> str:
    # Explicit selection wins (if configured)
    if EMAIL_PROVIDER == "resend" and resend_is_configured():
        return "resend"
    if EMAIL_PROVIDER == "smtp" and smtp_is_configured():
        return "smtp"
    # Fallback preference: Resend first (more scalable)
    if resend_is_configured():
        return "resend"
    if smtp_is_configured():
        return "smtp"
    return "none"


def _build_otp_content(otp: str, minutes_valid: int = 10) -> Tuple[str, str]:
    subject = "Your KnowEasy login code"
    text = (
        f"Your KnowEasy login code is: {otp}\n\n"
        f"This code expires in {minutes_valid} minutes.\n"
        "If you didn't request this, you can ignore this email.\n"
    )

    html = f"""<!doctype html>
<html>
  <body style="margin:0;padding:0;background:#f7f7f7;font-family:Arial,Helvetica,sans-serif;">
    <div style="max-width:520px;margin:32px auto;background:#ffffff;border-radius:12px;overflow:hidden;border:1px solid #eaeaea;">
      <div style="padding:20px 22px;background:#111827;color:#ffffff;">
        <div style="font-size:16px;font-weight:700;letter-spacing:0.2px;">KnowEasy</div>
        <div style="opacity:0.9;margin-top:4px;">Login verification</div>
      </div>
      <div style="padding:22px;color:#111827;">
        <div style="font-size:14px;line-height:1.5;">Use this code to login:</div>
        <div style="margin:14px 0 16px 0;font-size:28px;font-weight:800;letter-spacing:4px;">{otp}</div>
        <div style="font-size:12px;color:#6b7280;line-height:1.5;">Expires in {minutes_valid} minutes.</div>
      </div>
      <div style="padding:14px 22px;background:#f9fafb;color:#6b7280;font-size:12px;line-height:1.4;">
        If you didn't request this, ignore this email.
      </div>
    </div>
  </body>
</html>
"""
    return subject, text, html


def _send_via_smtp(to_email: str, subject: str, text: str, html: str) -> None:
    msg = EmailMessage()
    msg["From"] = f"{SMTP_FROM_NAME} <{EMAIL_FROM}>" if SMTP_FROM_NAME else EMAIL_FROM
    msg["To"] = to_email
    msg["Subject"] = subject
    msg.set_content(text)
    msg.add_alternative(html, subtype="html")

    if SMTP_SECURITY == "ssl":
        context = ssl.create_default_context()
        with smtplib.SMTP_SSL(SMTP_HOST, SMTP_PORT, context=context, timeout=25) as server:
            server.login(SMTP_USER, SMTP_PASS)
            server.send_message(msg)
        return

    # default STARTTLS
    with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=25) as server:
        server.ehlo()
        server.starttls(context=ssl.create_default_context())
        server.ehlo()
        server.login(SMTP_USER, SMTP_PASS)
        server.send_message(msg)


def _send_via_resend(to_email: str, subject: str, text: str, html: str) -> None:
    payload = {
        "from": EMAIL_FROM,
        "to": [to_email],
        "subject": subject,
        "text": text,
        "html": html,
    }
    data = json.dumps(payload).encode("utf-8")
    req = request.Request(
        RESEND_ENDPOINT,
        data=data,
        headers={
            "Authorization": f"Bearer {RESEND_API_KEY}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with request.urlopen(req, timeout=25) as resp:
            # Expect 200/201; just read to finish request
            resp.read()
    except error.HTTPError as e:
        body = e.read().decode("utf-8", errors="ignore")
        raise RuntimeError(f"Resend HTTP {e.code}: {body}") from e
    except Exception as e:
        raise RuntimeError(f"Resend send failed: {e}") from e


def send_otp_email(to_email: str, otp: str, minutes_valid: int = 10) -> None:
    """Send an OTP email. Raises RuntimeError on failure."""
    provider = _choose_provider()
    if provider == "none":
        raise RuntimeError(
            "Email is not configured. Set EMAIL_PROVIDER and either RESEND_API_KEY+EMAIL_FROM (Resend) "
            "or SMTP_HOST/SMTP_USER/SMTP_PASS/EMAIL_FROM (SMTP)."  # noqa: E501
        )

    subject, text, html = _build_otp_content(otp=otp, minutes_valid=minutes_valid)

    if provider == "resend":
        _send_via_resend(to_email, subject, text, html)
        return
    if provider == "smtp":
        _send_via_smtp(to_email, subject, text, html)
        return

    raise RuntimeError(f"Unsupported EMAIL_PROVIDER: {provider}")


def email_is_configured() -> bool:
    """True if either Resend or SMTP is configured for sending transactional email."""
    return resend_is_configured() or smtp_is_configured()

