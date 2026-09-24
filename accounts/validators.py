import re

from django.core.exceptions import ValidationError
from django.utils.translation import gettext as _


class MixedPasswordValidator:
    """Matches the live Neuromed signup rule: 8+ chars, letters, numbers, symbol."""

    def validate(self, password, user=None):
        if (
            len(password) < 8
            or not re.search(r"[A-Za-z]", password)
            or not re.search(r"\d", password)
            or not re.search(r"[^A-Za-z0-9]", password)
        ):
            raise ValidationError(
                _("Use 8+ characters with letters, numbers, and a symbol."),
                code="password_complexity",
            )

    def get_help_text(self):
        return _("8+ characters, with letters, numbers, and a symbol.")
