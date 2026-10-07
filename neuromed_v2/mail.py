"""Shared outbound email helper (Django mail API).

Every email in the app goes through send_html_email(), so the transport
(console locally, Amazon SES on AWS) can change without touching features.
See Docs/SES_EMAIL_SETUP.md.

Keep patient details (diagnoses, transcripts, summaries) out of subjects and
bodies — send a link back to the app instead.
"""

from __future__ import annotations

import logging

from django.conf import settings
from django.core.mail import EmailMessage

logger = logging.getLogger(__name__)


class MailNotConfiguredError(Exception):
    """Raised when DEFAULT_FROM_EMAIL or a recipient is missing."""


def email_ready() -> bool:
    return bool((getattr(settings, "DEFAULT_FROM_EMAIL", "") or "").strip())


def send_html_email(
    *,
    to: list[str],
    subject: str,
    html_body: str,
    reply_to: list[str] | None = None,
) -> None:
    """Send one HTML email via the configured Django email backend."""
    from_email = (settings.DEFAULT_FROM_EMAIL or "").strip()
    if not from_email:
        raise MailNotConfiguredError("DEFAULT_FROM_EMAIL is not configured.")

    recipients = [addr.strip() for addr in to if (addr or "").strip()]
    if not recipients:
        raise MailNotConfiguredError("No recipient address provided.")

    message = EmailMessage(
        subject=subject,
        body=html_body,
        from_email=from_email,
        to=recipients,
        reply_to=reply_to or None,
    )
    message.content_subtype = "html"
    try:
        message.send(fail_silently=False)
    except Exception:
        # Do not log subject/body/recipients (may contain sensitive content).
        logger.exception("Outbound email send failed")
        raise
