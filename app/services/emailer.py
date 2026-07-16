"""SMTP transport for follow-up emails.

Stdlib only (smtplib + email.message). Credentials come from app config
(SMTP_* env vars); with no username/password configured the app treats
email as disabled and send_email raises EmailNotConfiguredError.
Error messages must never contain the password.
"""

from __future__ import annotations

import smtplib
import ssl
from email.message import EmailMessage
from email.utils import formataddr


class EmailNotConfiguredError(RuntimeError):
    """SMTP credentials are not set; sending is disabled."""


class EmailSendError(RuntimeError):
    """The SMTP conversation failed (connection, auth, or send)."""


def is_configured(config) -> bool:
    return bool(config.get("SMTP_USERNAME") and config.get("SMTP_PASSWORD"))


def _has_header_injection(*values: str) -> bool:
    # CRLF in a header value lets a crafted string add extra headers/recipients.
    return any("\r" in v or "\n" in v for v in values)


def send_email(config, *, to: str, subject: str, body: str) -> None:
    if not is_configured(config):
        raise EmailNotConfiguredError(
            "Email sending is not configured. Set SMTP_USERNAME and SMTP_PASSWORD in .env."
        )
    if not to.strip() or not subject.strip() or not body.strip():
        raise EmailSendError("Recipient, subject and message are all required.")
    if _has_header_injection(to, subject):
        raise EmailSendError("Recipient and subject must not contain line breaks.")

    username = config["SMTP_USERNAME"]
    # Google displays app passwords in spaced groups; stripping is always safe.
    password = config["SMTP_PASSWORD"].replace(" ", "")

    message = EmailMessage()
    message["From"] = formataddr((config.get("MAIL_FROM_NAME") or username, username))
    message["To"] = to.strip()
    message["Subject"] = subject.strip()
    message.set_content(body)

    try:
        with smtplib.SMTP(config["SMTP_HOST"], config["SMTP_PORT"], timeout=20) as smtp:
            # SMTP_STARTTLS=0 targets a local test sink with no TLS or auth
            # (never a real provider).
            if config.get("SMTP_STARTTLS", True):
                smtp.starttls(context=ssl.create_default_context())
                smtp.login(username, password)
            smtp.send_message(message)
    except smtplib.SMTPAuthenticationError as exc:
        raise EmailSendError(
            "The mail server rejected the login - check SMTP_USERNAME and "
            "SMTP_PASSWORD (Gmail needs an App Password, not your normal password)."
        ) from exc
    except (smtplib.SMTPException, OSError) as exc:
        raise EmailSendError(f"Could not send the email ({exc.__class__.__name__}).") from exc
