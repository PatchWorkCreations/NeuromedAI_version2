"""
See CLAUDE.md boundary #4: the free-tier boundary changes in v2. Gate
CareCircle sharing, extended history, and voice narration here — never
gate VisitRecording creation or summarization (visits app). That's the
one rule this whole app exists to enforce correctly.

StoreKit models only get added here if the native-iOS decision in
ARCHITECTURE.md lands that way — don't scaffold apple_iap.py speculatively.
"""
from django.conf import settings
from django.db import models


class Subscription(models.Model):
    class Plan(models.TextChoices):
        FREE = "free", "Free"
        PLUS = "plus", "Aira Plus"

    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    plan = models.CharField(max_length=20, choices=Plan.choices, default=Plan.FREE)
    square_customer_id = models.CharField(max_length=255, blank=True)
    current_period_end = models.DateTimeField(null=True, blank=True)

    def can_use_care_circle(self) -> bool:
        return self.plan == self.Plan.PLUS

    def can_record_and_summarize(self) -> bool:
        return True  # always — see boundary #4, this is never gated
