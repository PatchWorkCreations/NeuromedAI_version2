"""
Google reCAPTCHA v2 ("I'm not a robot" checkbox) for public forms that bots
target: sign-up, log-in, forgot password, and any future contact form.

The checkbox widget puts a token in the form; verify() checks it with Google's
siteverify endpoint. With no keys set (local dev, tests) the check is off.

Only load the widget on these public pages — never on chat, visits or
documents, so Google's script never runs next to health information.
"""
import logging

import requests
from django import forms
from django.conf import settings

logger = logging.getLogger(__name__)

VERIFY_URL = "https://www.google.com/recaptcha/api/siteverify"
TOKEN_FIELD = "g-recaptcha-response"
FAILED_MESSAGE = "Please tick “I’m not a robot” and try again."


def enabled() -> bool:
    return bool(settings.RECAPTCHA_SITE_KEY and settings.RECAPTCHA_SECRET_KEY)


def verify(token: str, form_name: str, remote_ip: str = "") -> bool:
    if not enabled():
        return True
    if not token:
        logger.info("recaptcha form=%s result=not-ticked", form_name)
        return False
    data = {"secret": settings.RECAPTCHA_SECRET_KEY, "response": token}
    if remote_ip:
        data["remoteip"] = remote_ip
    try:
        r = requests.post(VERIFY_URL, data=data, timeout=5)
        result = r.json()
    except (requests.RequestException, ValueError) as exc:
        # Google unreachable: let people in rather than lock patients out of their account.
        logger.warning("recaptcha form=%s result=unreachable error=%s", form_name, type(exc).__name__)
        return True
    ok = result.get("success") is True
    logger.info(
        "recaptcha form=%s ok=%s host=%s errors=%s",
        form_name, ok, result.get("hostname", ""), ",".join(result.get("error-codes", [])),
    )
    return ok


class RecaptchaFormMixin:
    """Add to a Django form and set recaptcha_form; call check_recaptcha() first in clean()."""

    recaptcha_form = ""

    def check_recaptcha(self):
        if not verify(self.data.get(TOKEN_FIELD, ""), self.recaptcha_form):
            raise forms.ValidationError(FAILED_MESSAGE, code="recaptcha")
