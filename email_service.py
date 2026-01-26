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
import logging
from email.message import EmailMessage
from typing import Optional, Tuple
from urllib import request, error

logger = logging.getLogger("knoweasy-engine-api.email")


def _env(name: str, default: str = "") -> str:
    v = os.getenv(name)
    return (v if v is not None else default).strip()


# Generic "from" settings (recommended)
# NOTE: earlier project versions used FROM_EMAIL; keep compatibility.
EMAIL_FROM = _env("EMAIL_FROM") or _env("FROM_EMAIL") or _env("SMTP_FROM")  # allow legacy vars
SMTP_FROM_NAME = _env("SMTP_FROM_NAME") or _env("FROM_NAME", "KnowEasy")

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


def email_is_configured() -> bool:
    """True if either Resend or SMTP is usable."""
    return _choose_provider() != "none"


def email_provider_debug() -> dict:
    """Non-sensitive diagnostics to understand provider selection in prod logs."""
    provider = _choose_provider()
    return {
        "provider": provider,
        "email_provider_env": EMAIL_PROVIDER or "",
        "has_resend_key": bool(RESEND_API_KEY),
        "has_email_from": bool(EMAIL_FROM),
        "smtp_host_set": bool(SMTP_HOST),
        "smtp_user_set": bool(SMTP_USER),
        "smtp_pass_set": bool(SMTP_PASS),
    }


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
    # Resend recommends a "Name <email@domain>" format for From.
    from_value = EMAIL_FROM
    if from_value and "<" not in from_value and ">" not in from_value and SMTP_FROM_NAME:
        from_value = f"{SMTP_FROM_NAME} <{from_value}>"

    payload = {
        "from": from_value,
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
            body = resp.read().decode("utf-8", errors="ignore")
            try:
                logger.info(f"Resend ok status={getattr(resp, 'status', 'unknown')} to={to_email}")
            except Exception:
                pass
            # keep body unused; it's sometimes JSON with id
            _ = body
    except error.HTTPError as e:
        body = e.read().decode("utf-8", errors="ignore")
        try:
            logger.error(f"Resend HTTP {e.code} to={to_email} body={body[:300]}")
        except Exception:
            pass
        raise RuntimeError(f"Resend HTTP {e.code}: {body}") from e
    except Exception as e:
        try:
            logger.exception(f"Resend send failed to={to_email}: {e}")
        except Exception:
            pass
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


# ---------------------------------------------------------------------------
# Payment receipt email (Phase-2)
# ---------------------------------------------------------------------------

def _build_payment_receipt_content(
    *,
    plan_label: str,
    billing_cycle: str,
    amount_paise: int,
    currency: str,
    razorpay_order_id: str,
    razorpay_payment_id: str,
    paid_at_iso: str,
) -> Tuple[str, str, str]:
    """Build receipt subject + text + html."""

    amount = 0.0
    try:
        amount = float(int(amount_paise) / 100.0)
    except Exception:
        amount = 0.0

    plan_label_clean = (plan_label or "").strip() or "KnowEasy"
    cycle = (billing_cycle or "monthly").strip().lower() or "monthly"
    cycle_label = "Yearly" if cycle == "yearly" else "Monthly"
    cur = (currency or "INR").strip().upper() or "INR"

    subject = f"Payment received • {plan_label_clean} ({cycle_label})"

    text = (
        f"Payment received for {plan_label_clean} ({cycle_label}).\n\n"
        f"Amount: {cur} {amount:.2f}\n"
        f"Order ID: {razorpay_order_id}\n"
        f"Payment ID: {razorpay_payment_id}\n"
        f"Paid at: {paid_at_iso}\n\n"
        "Thank you for choosing KnowEasy.\n"
    )

    support = _env("SUPPORT_EMAIL") or _env("EMAIL_FROM")
    brand = _env("BRAND_NAME", "KnowEasy")

    html = f"""<!doctype html>
<html>
  <body style="margin:0;padding:0;background:#f7f7f7;font-family:Arial,Helvetica,sans-serif;">
    <div style="max-width:560px;margin:28px auto;background:#ffffff;border-radius:14px;overflow:hidden;border:1px solid #eaeaea;">
      <div style="padding:18px 22px;background:#111827;color:#ffffff;">
        <div style="font-size:16px;font-weight:800;letter-spacing:0.2px;">{brand}</div>
        <div style="opacity:0.92;margin-top:4px;">Payment receipt</div>
      </div>
      <div style="padding:22px;color:#111827;">
        <div style="font-size:15px;line-height:1.6;">We received your payment successfully.</div>

        <div style="margin-top:14px;border:1px solid #eef2f7;border-radius:12px;overflow:hidden;">
          <div style="padding:12px 14px;background:#f9fafb;font-weight:800;">Summary</div>
          <div style="padding:14px 14px;font-size:13px;line-height:1.7;">
            <div><b>Plan:</b> {plan_label_clean}</div>
            <div><b>Billing cycle:</b> {cycle_label}</div>
            <div><b>Amount:</b> {cur} {amount:.2f}</div>
            <div style="margin-top:10px;"><b>Order ID:</b> {razorpay_order_id}</div>
            <div><b>Payment ID:</b> {razorpay_payment_id}</div>
            <div><b>Paid at:</b> {paid_at_iso}</div>
          </div>
        </div>

        <div style="margin-top:14px;font-size:12px;color:#6b7280;line-height:1.6;">
          If you have any questions, reply to this email or contact <b>{support}</b>.
        </div>
      </div>
      <div style="padding:14px 22px;background:#f9fafb;color:#6b7280;font-size:12px;line-height:1.4;">
        This is an automated receipt for your records.
      </div>
    </div>
  </body>
</html>
"""

    return subject, text, html


def send_payment_receipt_email(
    *,
    to_email: str,
    plan_label: str,
    billing_cycle: str,
    amount_paise: int,
    currency: str,
    razorpay_order_id: str,
    razorpay_payment_id: str,
    paid_at_iso: str,
) -> None:
    """Send a payment receipt email. Raises RuntimeError on failure."""
    provider = _choose_provider()
    if provider == "none":
        raise RuntimeError("Email is not configured")

    subject, text, html = _build_payment_receipt_content(
        plan_label=plan_label,
        billing_cycle=billing_cycle,
        amount_paise=amount_paise,
        currency=currency,
        razorpay_order_id=razorpay_order_id,
        razorpay_payment_id=razorpay_payment_id,
        paid_at_iso=paid_at_iso,
    )

    if provider == "resend":
        _send_via_resend(to_email, subject, text, html)
        return
    if provider == "smtp":
        _send_via_smtp(to_email, subject, text, html)
        return

    raise RuntimeError(f"Unsupported EMAIL_PROVIDER: {provider}")
