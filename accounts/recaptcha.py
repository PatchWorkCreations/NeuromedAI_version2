"""
Google reCAPTCHA v3 (classic, score-based) for public forms that bots target:
sign-up, log-in, forgot password, and any future contact form.

The browser gets a token for a named action; verify() checks it with Google's
siteverify endpoint and accepts it only if it is valid, was issued for the same
action, and scores at least RECAPTCHA_MIN_SCORE. With no secret key set
(local dev, tests) the check is off.

Only load the script on these public pages — never on chat, visits or
documents, so Google's script never runs next to health information.
"""
import logging

import requests
from django import forms
from django.conf import settings

logger = logging.getLogger(__name__)

VERIFY_URL = "https://www.google.com/recaptcha/api/siteverify"
TOKEN_FIELD = "g-recaptcha-response"
FAILED_MESSAGE = "We couldn’t confirm you’re not a robot. Please try again in a moment."


def enabled() -> bool:
    return bool(settings.RECAPTCHA_SITE_KEY and settings.RECAPTCHA_SECRET_KEY)


def verify(token: str, action: str, remote_ip: str = "") -> bool:
    if not enabled():
        return True
    if not token:
        logger.info("recaptcha action=%s result=missing-token", action)
        return False
    data = {"secret": settings.RECAPTCHA_SECRET_KEY, "response": token}
    if remote_ip:
        data["remoteip"] = remote_ip
    try:
        r = requests.post(VERIFY_URL, data=data, timeout=5)
        result = r.json()
    except (requests.RequestException, ValueError) as exc:
        # Google unreachable: let people in rather than lock patients out of their account.
        logger.warning("recaptcha action=%s result=unreachable error=%s", action, type(exc).__name__)
        return True
    ok = (
        result.get("success") is True
        and result.get("action") == action
        and float(result.get("score", 0)) >= settings.RECAPTCHA_MIN_SCORE
    )
    logger.info(
        "recaptcha action=%s ok=%s score=%s errors=%s",
        action, ok, result.get("score"), ",".join(result.get("error-codes", [])),
    )
    return ok


class RecaptchaFormMixin:
    """Add to a Django form and set recaptcha_action; call check_recaptcha() first in clean()."""

    recaptcha_action = ""

    def check_recaptcha(self):
        if not verify(self.data.get(TOKEN_FIELD, ""), self.recaptcha_action):
            raise forms.ValidationError(FAILED_MESSAGE, code="recaptcha")
